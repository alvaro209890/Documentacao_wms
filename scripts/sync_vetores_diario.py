#!/usr/bin/env python3
"""Atualiza o espelho vetorial que atende o GeoServer e o Optimus Geo."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
from time import monotonic, sleep
from zipfile import ZipFile
from zoneinfo import ZoneInfo

from osgeo import gdal, ogr
import requests

RAIZ = Path("/media/server/HD Backup/VETOR/Espelho_Diario")
LEGADO = Path.home() / ".local/bin/sync_car_digital.py"
TZ = ZoneInfo("America/Sao_Paulo")
WMS = "http://127.0.0.1:8081/geoserver"
WORKSPACE = "cbers"
PUBLICADOS = ("simcar", "fiscalizacao", "fundiario")
GRUPOS = ("car", "fundiario", "fiscalizacao", "pamgia", "simcar")
PAMGIA = ("https://pamgia.ibama.gov.br/server/rest/services/01_Publicacoes_Bases/"
          "{}/FeatureServer/0/query")
MT = (-62.0, -18.5, -49.5, -6.9)
UA = {"User-Agent": "Mozilla/5.0 (optimus-geo)"}
COMPONENTES = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".cst"}
NOME = re.compile(r"[a-z0-9_]+")
gdal.UseExceptions()


class Falha(RuntimeError):
    """Mensagem técnica segura para o journal."""


@dataclass(frozen=True)
class Fonte:
    grupo: str
    nome: str
    url: str
    tipo: str
    camada: str
    parametros: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)


def modulo(path, nome):
    spec = importlib.util.spec_from_file_location(nome, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = obj
    spec.loader.exec_module(obj)
    return obj


def agora():
    return datetime.now(TZ)


def gravar(path, payload):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8") as arq:
        tmp = Path(arq.name)
        json.dump(payload, arq, ensure_ascii=False, indent=2)
        arq.flush()
        os.fsync(arq.fileno())
    try:
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def ler(path):
    return json.loads(path.read_text()) if path.exists() else {}


def emitir(**campos):
    print(json.dumps(campos, ensure_ascii=False), flush=True)


def get(url, *, parametros, headers, timeout=90, stream=False):
    for tentativa in range(2):
        try:
            resp = requests.get(url, params=parametros, headers=headers, stream=stream, timeout=(15, timeout))
            if resp.ok:
                return resp
            status = resp.status_code
            resp.close()
            if status < 500 and status != 429:
                raise Falha(f"HTTP {status}")
            causa = f"HTTP {status}"
        except requests.RequestException as exc:
            causa = type(exc).__name__
        if tentativa == 0:
            sleep(2)
    raise Falha(causa)


def total_wfs(url, parametros, headers):
    with get(url, parametros={**parametros, "resultType": "hits"}, headers=headers, timeout=22) as resp:
        achou = re.search(r'(?:numberMatched|numberOfFeatures)="(\d+)"', resp.text)
    if not achou:
        raise Falha("WFS não informou a contagem de feições")
    return int(achou[1])


def parametros_wfs(camada):
    return {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": camada}


def baixar_wfs(fonte, pasta):
    params = parametros_wfs(fonte.camada) | fonte.parametros
    total = total_wfs(fonte.url, params, fonte.headers)
    emitir(grupo=fonte.grupo, camada=fonte.nome, status="baixando", feicoes=total)
    zip_path = pasta / "origem.zip"
    with get(fonte.url, parametros=params | {"outputFormat": "SHAPE-ZIP"}, headers=fonte.headers,
             timeout=600, stream=True) as resp, zip_path.open("wb") as arq:
        for parte in resp.iter_content(1024 * 1024):
            arq.write(parte)
    return zip_path, total


def desempacotar(zip_path, destino, nome):
    destino.mkdir(exist_ok=True)
    with ZipFile(zip_path) as z:
        shapes = [m for m in z.namelist() if PurePosixPath(m).suffix.lower() == ".shp"]
        if len(shapes) != 1:
            raise Falha(f"ZIP tem {len(shapes)} shapefiles, esperado um")
        alvo = PurePosixPath(shapes[0])
        for membro in z.namelist():
            p = PurePosixPath(membro)
            ext = p.suffix.lower()
            if p.with_suffix("") != alvo.with_suffix("") or ext not in COMPONENTES:
                continue
            with z.open(membro) as origem, (destino / (nome + ext)).open("wb") as saida:
                shutil.copyfileobj(origem, saida, 1024 * 1024)
    shp = destino / (nome + ".shp")
    if not all(shp.with_suffix(ext).is_file() for ext in (".shp", ".shx", ".dbf", ".prj")):
        raise Falha("componentes do shapefile incompletos")
    return shp


def baixar_pamgia(fonte, pasta):
    query = {"where": "1=1", "geometry": ",".join(map(str, MT)), "geometryType": "esriGeometryEnvelope",
             "inSR": 4674, "spatialRel": "esriSpatialRelIntersects", "returnIdsOnly": "true", "f": "json"}
    with get(fonte.url, parametros=query, headers=UA) as resp:
        d = resp.json()
    ids = d.get("objectIds")
    campo = (d.get("objectIdFieldName") or "").lower()
    if not ids or not campo or len(ids) != len(set(ids)):
        raise Falha("PAMGIA não retornou identificadores válidos")
    ids.sort()
    path = pasta / "origem.geojson"
    with path.open("w", encoding="utf-8") as arq:
        arq.write('{"type":"FeatureCollection","features":[')
        for i in range(0, len(ids), 400):
            lote = ids[i:i + 400]
            q = {"objectIds": ",".join(map(str, lote)), "outFields": "*", "returnGeometry": "true",
                 "outSR": 4674, "f": "geojson"}
            with get(fonte.url, parametros=q, headers=UA) as resp:
                feicoes = resp.json().get("features")
            if not isinstance(feicoes, list):
                raise Falha("PAMGIA respondeu sem feições no lote")
            obtidos = {next((v for k, v in (f.get("properties") or {}).items() if k.lower() == campo), None): f
                       for f in feicoes}
            if set(lote) != obtidos.keys() or len(lote) != len(feicoes):
                raise Falha("PAMGIA devolveu lote incompleto ou duplicado")
            for j, oid in enumerate(lote):
                if i or j:
                    arq.write(",")
                json.dump(obtidos[oid], arq, sort_keys=True, separators=(",", ":"))
        arq.write("]}")
    return path, len(ids)


def identidade(arquivos):
    digest = hashlib.sha256()
    for path in sorted(arquivos):
        digest.update(path.suffix.encode() + b"\0" + str(path.stat().st_size).encode() + b"\0")
        with path.open("rb") as arq:
            if path.suffix == ".dbf":
                cab = arq.read(4)
                digest.update(cab[:1] + b"\0\0\0")
            while bloco := arq.read(1024 * 1024):
                digest.update(bloco)
    return digest.hexdigest()


def validar(path, total, *, campo=None, invertido=False, vazio_confirmado=False):
    ds = ogr.Open(str(path), 0)
    layer = ds.GetLayer(0) if ds else None
    if layer is None:
        raise Falha("GDAL não abriu a camada")
    count = layer.GetFeatureCount()
    if count != total or (count == 0 and not vazio_confirmado):
        raise Falha(f"contagem divergente ou vazia: origem {total}, arquivo {count}")
    if layer.GetSpatialRef() is None:
        raise Falha("CRS ausente")
    if count:
        x0, x1, y0, y1 = layer.GetExtent()
        if invertido:
            x0, x1, y0, y1 = y0, y1, x0, x1
        if not (-75 <= x0 < x1 <= -30 and -35 <= y0 < y1 <= 7):
            raise Falha("extensão fora das coordenadas esperadas")
    if campo and layer.GetLayerDefn().GetFieldIndex(campo) < 0:
        raise Falha(f"campo {campo} ausente")


def converter(original, target, nome, charset=None):
    cmd = ["ogr2ogr", "-f", "GPKG", str(target), str(original), "-nln", nome,
           "-nlt", "PROMOTE_TO_MULTI", "-t_srs", "EPSG:4674", "-lco", "SPATIAL_INDEX=YES",
           "-lco", "GEOMETRY_NAME=the_geom"]
    if original.suffix == ".geojson":
        cmd.extend(["-s_srs", "EPSG:4674"])
    if charset:
        cmd.extend(["--config", "SHAPE_ENCODING", charset])
    feito = subprocess.run(cmd, capture_output=True, timeout=3600)
    if feito.returncode:
        raise Falha(f"ogr2ogr retornou código {feito.returncode}")


def preparar(fonte, pasta, store, legado, reuso):
    objeto = pasta / "objeto"
    objeto.mkdir()
    invertido = fonte.grupo == "fundiario"
    vazio_confirmado = False
    if fonte.tipo == "pamgia":
        original, total = baixar_pamgia(fonte, pasta)
        digest = identidade([original])
    else:
        if reuso and (reuso / (fonte.nome + ".zip")).is_file():
            zip_path = reuso / (fonte.nome + ".zip")
            total = int(zip_path.with_suffix(".count").read_text())
        else:
            zip_path, total = baixar_wfs(fonte, pasta)
        if total == 0 and store is not None:
            vazio_confirmado = total_wfs(
                f"{WMS}/{WORKSPACE}/wfs", parametros_wfs(f"{WORKSPACE}:{fonte.nome}"), UA
            ) == 0
        original = desempacotar(zip_path, objeto, fonte.nome)
        digest = identidade(objeto.iterdir())
        validar(original, total, campo="NUMERO" if fonte.grupo == "car" else None,
                invertido=invertido, vazio_confirmado=vazio_confirmado)
    gpkg = store is None or store.get("type", "").lower() == "geopackage"
    if gpkg:
        target = objeto / (fonte.nome + ".gpkg")
        converter(original, target, fonte.nome, legado.zip_charset(zip_path) if fonte.tipo == "wfs" else None)
        validar(target, total, campo="NUMERO" if fonte.grupo == "car" else None,
                invertido=invertido, vazio_confirmado=vazio_confirmado)
        for path in objeto.iterdir():
            if path != target:
                path.unlink()
        if fonte.grupo == "car":
            import sqlite3
            with sqlite3.connect(target) as banco:
                banco.execute(f'CREATE INDEX IF NOT EXISTS idx_numero ON "{fonte.nome}" ("NUMERO")')
    else:
        if any(p.suffix in {".shp", ".dbf"} and p.stat().st_size > 1_900_000_000 for p in objeto.iterdir()):
            raise Falha("camada cresceu além do limite do datastore Shapefile")
        target = original
        ds = ogr.Open(str(target), 1)
        if ds:
            ds.ExecuteSQL(f'CREATE SPATIAL INDEX ON "{fonte.nome}"')
            ds = None
    return objeto, target.name, digest, total


def parametro_store(store):
    return "database" if store.get("type", "").lower() == "geopackage" else "url"


def publicavel(store, path=None):
    chave = parametro_store(store)
    params = store["connectionParameters"]["entry"]
    entradas = [dict(e) for e in params]
    entry = next(e for e in entradas if e["@key"] == chave)
    if path is not None:
        entry["$"] = f"file:{path}" if chave == "database" else f"file:{path.parent}/"
    return {"dataStore": {"name": store["name"], "type": store["type"], "enabled": store["enabled"],
                          "connectionParameters": {"entry": entradas}}}


def publicar(sess, legado, store, target, total):
    nome = store["name"]
    rota = f"/rest/workspaces/{WORKSPACE}/datastores/{nome}.json"
    antigo = publicavel(store)
    novo = publicavel(store, target)
    if antigo != novo:
        try:
            resp = legado.rest_put(sess, rota, json_body=novo)
            if resp.status_code != 200:
                raise Falha(f"GeoServer PUT HTTP {resp.status_code}")
            contado = total_wfs(f"{WMS}/{WORKSPACE}/wfs", parametros_wfs(f"{WORKSPACE}:{nome}"), UA)
            confirmado = legado.get_datastore(sess, nome)
            def destino(payload):
                entradas = payload["dataStore"]["connectionParameters"]["entry"]
                return next(e["$"].rstrip("/") for e in entradas if e["@key"] == parametro_store(store))
            if contado != total or not confirmado or destino(publicavel(confirmado)) != destino(novo):
                raise Falha(f"GeoServer não confirmou a versão publicada ({contado}/{total} feições)")
        except Exception:
            recuperou = legado.rest_put(sess, rota, json_body=antigo)
            if recuperou.status_code != 200:
                raise Falha(f"rollback do datastore falhou HTTP {recuperou.status_code}")
            raise


def reter(pasta, anteriores, atual):
    versoes = (anteriores + [atual])[-3:]
    gravar(pasta / "estado.json", {"origem": atual["origem"], "versoes": versoes})
    ativos = {v["objeto"] for v in versoes}
    expirados = {v["objeto"] for v in anteriores} - ativos
    for digest in expirados:
        alvo = pasta / digest
        if re.fullmatch(r"[0-9a-f]{64}", digest) and alvo.is_dir() and not alvo.is_symlink():
            shutil.rmtree(alvo)
    return versoes


def atualizar(fonte, legado, reuso, apenas_preparar):
    if not NOME.fullmatch(fonte.nome):
        raise Falha("nome inválido")
    pasta = RAIZ / fonte.grupo / fonte.nome
    pasta.mkdir(parents=True, exist_ok=True)
    estado_path = pasta / "estado.json"
    estado = ler(estado_path)
    anteriores = estado.get("versoes", [])
    dia = agora().date().isoformat()
    if anteriores and anteriores[-1]["dia"] == dia and not apenas_preparar:
        emitir(grupo=fonte.grupo, camada=fonte.nome, status="ja_validada", dia=dia)
        return
    inicio = monotonic()
    sess = legado.session() if fonte.grupo in PUBLICADOS else None
    try:
        store = legado.get_datastore(sess, fonte.nome) if sess else None
        if sess and not store:
            raise Falha("datastore existente não localizado")
        with tempfile.TemporaryDirectory(prefix=".prepara-", dir=pasta, ignore_cleanup_errors=True) as d:
            objeto, nome_arquivo, digest, total = preparar(fonte, Path(d), store, legado, reuso)
            final = pasta / digest
            target = final / nome_arquivo
            if not final.exists():
                objeto.rename(final)
            if not target.is_file():
                raise Falha("objeto local não contém o arquivo esperado")
            if apenas_preparar:
                emitir(grupo=fonte.grupo, camada=fonte.nome, status="preparada", feicoes=total)
                return
            if sess:
                publicar(sess, legado, store, target, total)
            atual = {"dia": dia, "capturado_em": agora().isoformat(), "objeto": digest,
                     "arquivo": nome_arquivo, "feicoes": total, "origem": fonte.camada}
            versoes = reter(pasta, anteriores, atual)
            emitir(grupo=fonte.grupo, camada=fonte.nome, status="validada", feicoes=total,
                   reaproveitada=any(v["objeto"] == digest for v in anteriores),
                   versoes=len(versoes), segundos=round(monotonic() - inicio, 1))
    finally:
        if sess:
            sess.close()


def fontes(legacy, grupos):
    for grupo in grupos:
        if grupo in PUBLICADOS:
            for item in legacy.load_sources(legacy.DOMAINS_BY_KEY[grupo]):
                if item.source_type != "wfs_shape_zip":
                    raise Falha(f"tipo de fonte não tratado: {item.source_type}")
                params, _ = legacy.split_wfs_params(item.params)
                headers = {**UA, **item.headers}
                yield Fonte(grupo, item.store_name, item.wfs_url, "wfs", item.type_name, params, headers)
        if grupo == "car":
            sys.path.insert(0, str(Path.home() / ".local/share/imap-agentes/lib"))
            from imap_agentes import geo
            for nome, camada in (("car_analisado", "SIMCAR:SIMCAR_SIMCAR_ANALISADO"),
                                 ("car_em_analise", "SIMCAR:SIMCAR_SIMCAR_EM_ANALISE")):
                yield Fonte(grupo, nome, f"{geo.GEOSERVER}/wfs", "wfs", camada, {"authkey": geo.authkey()}, UA)
        if grupo == "pamgia":
            for nome in ("adm_embargos_ibama_a", "adm_embargo_icmbio_a"):
                yield Fonte(grupo, nome, PAMGIA.format(nome), "pamgia", nome, headers=UA)


def drive_mensal():
    """Mantém o espelho mensal no Drive a partir dos arquivos locais já disponíveis."""
    legacy = modulo(LEGADO, "sync_car_digital")
    upload = modulo(Path.home() / ".local/bin/upload_simcar_digital_drive.py", "upload_simcar_digital_drive")
    mes = agora().strftime("%Y-%m")
    estado = ler(upload.STATE_PATH)
    data_upload = estado.get("manifest_generated_at") or estado.get("last_uploaded_at") or ""
    if data_upload.startswith(mes):
        emitir(grupo="simcar_drive", status="mes_ja_publicado", mes=mes)
        return 0
    manifest = ler(legacy.DOMAINS_BY_KEY["simcar"].manifest_path)
    if not manifest.get("layers"):
        raise Falha("manifesto de origem do SIMCAR Digital indisponível")
    atualizadas = 0
    with tempfile.TemporaryDirectory(prefix="drive-mensal-", dir=RAIZ) as d:
        tmp = Path(d)
        for item in manifest["layers"]:
            nome = item["store_name"]
            pasta = RAIZ / "simcar" / nome
            versoes = ler(pasta / "estado.json").get("versoes", [])
            if not versoes:
                continue
            v = versoes[-1]
            arquivo = pasta / v["objeto"] / v["arquivo"]
            if arquivo.suffix != ".shp":
                origem = tmp / nome / (nome + ".shp")
                origem.parent.mkdir()
                cmd = ["ogr2ogr", "-f", "ESRI Shapefile", str(origem), str(arquivo),
                       "-lco", "ENCODING=UTF-8"]
                if subprocess.run(cmd, capture_output=True, timeout=3600).returncode:
                    raise Falha(f"Falhou a conversão para Drive de {nome}")
                arquivo = origem
            zip_path = tmp / f"{nome}.zip"
            with ZipFile(zip_path, "w") as z:
                for ext in sorted(COMPONENTES):
                    p = arquivo.with_suffix(ext)
                    if p.is_file():
                        z.write(p, arcname=p.name)
            item["dataset_zip"] = str(zip_path)
            item["mirrored_at"] = v["capturado_em"]
            atualizadas += v["dia"].startswith(mes)
        if not atualizadas:
            emitir(grupo="simcar_drive", status="aguardando_camadas_do_mes", mes=mes)
            return 0
        for grupo in manifest.get("groups", []):
            if grupo.get("layers"):
                grupo["layers"] = manifest["layers"]
        stamp = agora()
        manifest.update(generated_at=stamp.isoformat(), snapshot=stamp.strftime("%Y%m%dT%H%M%S"))
        upload.MANIFEST_PATH = tmp / "manifest.json"
        gravar(upload.MANIFEST_PATH, manifest)
        sys.argv = [sys.argv[0]]
        return upload.main()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grupo", choices=GRUPOS, action="append")
    parser.add_argument("--camada", action="append")
    parser.add_argument("--reuso", type=Path)
    parser.add_argument("--preparar", action="store_true")
    parser.add_argument("--drive-mensal", action="store_true")
    args = parser.parse_args()
    RAIZ.mkdir(parents=True, exist_ok=True)
    lock_path = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "wms-vetores-diarios.lock"
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.drive_mensal:
            return drive_mensal()
        legado = modulo(LEGADO, "sync_car_digital")
        itens = [f for f in fontes(legado, args.grupo or GRUPOS) if not args.camada or f.nome in args.camada]
        if not itens:
            raise Falha("nenhuma camada selecionada")
        if shutil.disk_usage(RAIZ).free < 30 * 2**30:
            raise Falha("menos de 30 GiB livres para preparar as camadas")
        problema = False
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(atualizar, f, legado, args.reuso, args.preparar): f for f in itens}
            for fut in as_completed(futures):
                f = futures[fut]
                try:
                    fut.result()
                except Exception as exc:
                    causa = str(exc) if isinstance(exc, Falha) else type(exc).__name__
                    if isinstance(exc, OSError) and exc.errno:
                        causa += f" errno={exc.errno}"
                    emitir(grupo=f.grupo, camada=f.nome, status="falhou", causa=causa)
                    problema = True
        return int(problema)


if __name__ == "__main__":
    sys.exit(main())
