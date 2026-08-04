# -*- coding: utf-8 -*-
"""Gera, para cada camada raster do GeoServer, um estilo com esticamento FIXO.

Problema
--------
O estilo `landsat_rgb` (104 camadas) e o `raster` padrao (633 camadas) usam
realce automatico. Para dado que nao e Byte, o GeoServer calcula o esticamento
a partir dos pixels da janela pedida -- entao a MESMA area do chao volta com
cor diferente dependendo do BBOX. Num mapa do ArcMap com quadro principal +
minimapas, cada quadro e uma requisicao com extensao propria, e as cores nao
batem.

Solucao
-------
Um estilo por camada, com `StretchToMinimumMaximum` nos percentis 2/98 da cena
inteira (calculados uma vez, aqui). O mapeamento valor->cor passa a ser
absoluto: nao depende mais do recorte pedido.

Camadas Byte nao sao tocadas -- 8 bits ja sai como esta gravado, sem conversao,
entao a cor delas ja e estavel.

Uso (no servidor):
    python3 gerar_estilos_fixos.py --censo /tmp/censo.json --plano /tmp/plano.json
    python3 gerar_estilos_fixos.py --censo /tmp/censo.json --plano /tmp/plano.json --aplicar
    python3 gerar_estilos_fixos.py --reverter /tmp/plano.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys

import numpy as np
from osgeo import gdal

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

ESTILOS = "/home/server/geoserver_data/styles"
RAIZ = "/home/server/geoserver_data/workspaces"
LADO_ALVO = 1500          # lado maximo do overview usado para as estatisticas
PERCENTIS = (2.0, 98.0)


def escala(camada: str, caminho: str, bandas: int) -> list[tuple[int, int]] | None:
    """Percentis 2/98 por banda, ignorando nodata e a borda preta da cena."""
    ds = gdal.Open(caminho)
    usar = min(bandas, 3)
    b1 = ds.GetRasterBand(1)
    nivel = -1
    for i in range(b1.GetOverviewCount()):
        ov = b1.GetOverview(i)
        if max(ov.XSize, ov.YSize) <= LADO_ALVO:
            nivel = i
            break
    else:
        nivel = b1.GetOverviewCount() - 1

    def leitura(n: int) -> np.ndarray:
        banda = ds.GetRasterBand(n)
        fonte = banda.GetOverview(nivel) if nivel >= 0 else banda
        if nivel < 0 and max(banda.XSize, banda.YSize) > LADO_ALVO:
            passo = max(1, max(banda.XSize, banda.YSize) // LADO_ALVO)
            return banda.ReadAsArray(buf_xsize=banda.XSize // passo,
                                     buf_ysize=banda.YSize // passo).astype("float64")
        return fonte.ReadAsArray().astype("float64")

    planos = [leitura(n) for n in range(1, usar + 1)]
    forma = planos[0].shape
    if any(p.shape != forma for p in planos):
        return None

    valido = np.ones(forma, dtype=bool)
    for n, plano in enumerate(planos, start=1):
        nd = ds.GetRasterBand(n).GetNoDataValue()
        if nd is not None:
            valido &= plano != nd
        # Float32 do acervo tem NaN; sem isso o percentil sai nan e o SLD quebra
        # a camada inteira ("Error rendering coverage on the fast path").
        valido &= np.isfinite(plano)
    # borda preta: pixel zerado em todas as bandas
    valido &= ~np.all(np.stack(planos) == 0, axis=0)
    if valido.sum() < 1000:
        return None

    faixas = []
    for plano in planos:
        lo, hi = (float(v) for v in np.percentile(plano[valido], PERCENTIS))
        if not (np.isfinite(lo) and np.isfinite(hi)) or hi <= lo:
            return None
        faixas.append((lo, hi))
    return faixas


def num(v: float) -> str:
    """Inteiro sai sem casa decimal; Float32 preserva a precisao que importa."""
    return str(int(round(v))) if float(v).is_integer() or abs(v) >= 1000 else "%.6g" % v


def sld(camada_qualificada: str, nome_estilo: str, faixas: list[tuple[float, float]]) -> str:
    def canal(tag: str, n: int) -> str:
        lo, hi = faixas[n - 1]
        return ('        <%sChannel>\n'
                '          <SourceChannelName>%d</SourceChannelName>\n'
                '          <ContrastEnhancement><Normalize>\n'
                '            <VendorOption name="algorithm">StretchToMinimumMaximum</VendorOption>\n'
                '            <VendorOption name="minValue">%s</VendorOption>\n'
                '            <VendorOption name="maxValue">%s</VendorOption>\n'
                '          </Normalize></ContrastEnhancement>\n'
                '        </%sChannel>\n') % (tag, n, num(lo), num(hi), tag)

    if len(faixas) >= 3:
        canais = canal("Red", 1) + canal("Green", 2) + canal("Blue", 3)
    else:
        canais = canal("Gray", 1)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<StyledLayerDescriptor version="1.0.0"\n'
            '  xmlns="http://www.opengis.net/sld"\n'
            '  xmlns:ogc="http://www.opengis.net/ogc"\n'
            '  xmlns:xlink="http://www.w3.org/1999/xlink"\n'
            '  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
            '  <NamedLayer>\n'
            '    <Name>%s</Name>\n'
            '    <UserStyle>\n'
            '      <Name>%s</Name>\n'
            '      <Title>Esticamento fixo (p2-p98 da cena)</Title>\n'
            '      <Abstract>Realce absoluto: a cor nao depende do BBOX pedido.</Abstract>\n'
            '      <FeatureTypeStyle><Rule><RasterSymbolizer>\n'
            '        <Opacity>1.0</Opacity>\n'
            '        <ChannelSelection>\n%s'
            '        </ChannelSelection>\n'
            '      </RasterSymbolizer></Rule></FeatureTypeStyle>\n'
            '    </UserStyle>\n'
            '  </NamedLayer>\n'
            '</StyledLayerDescriptor>\n') % (camada_qualificada, nome_estilo, canais)


def descritor(id_estilo: str, nome: str) -> str:
    return ('<style>\n  <id>%s</id>\n  <name>%s</name>\n  <format>sld</format>\n'
            '  <languageVersion>\n    <version>1.0.0</version>\n  </languageVersion>\n'
            '  <filename>%s.sld</filename>\n</style>\n') % (id_estilo, nome, nome)


def caminho_layer_xml(ws: str, camada: str) -> str | None:
    dws = os.path.join(RAIZ, ws)
    for store in os.listdir(dws):
        p = os.path.join(dws, store, camada, "layer.xml")
        if os.path.isfile(p):
            return p
    return None


def planejar(censo: list[dict]) -> list[dict]:
    plano = []
    for i, reg in enumerate(censo, start=1):
        camada = reg["camada"]
        if reg.get("erro") or not reg.get("dtype"):
            plano.append({**reg, "acao": "pular", "motivo": reg.get("erro", "sem leitura")})
            continue
        if reg["dtype"] == "Byte":
            plano.append({**reg, "acao": "pular", "motivo": "ja e 8 bits, cor estavel"})
            continue
        alvo = reg.get("amostra") or reg["caminho"]
        try:
            faixas = escala(camada, alvo, reg["bandas"])
        except Exception as e:
            plano.append({**reg, "acao": "pular", "motivo": "erro nas estatisticas: %s" % str(e)[:80]})
            continue
        if not faixas:
            plano.append({**reg, "acao": "pular", "motivo": "estatisticas insuficientes"})
            continue
        nome = camada + "_fixo"
        plano.append({**reg, "acao": "aplicar", "faixas": faixas, "estilo": nome,
                      "estilo_id": "StyleInfoImpl-fixo-" + hashlib.sha1(nome.encode()).hexdigest()[:16]})
        if i % 25 == 0:
            print("  ... %d/%d" % (i, len(censo)), flush=True)
    return plano


def aplicar(plano: list[dict]) -> None:
    feitos = 0
    for reg in plano:
        if reg["acao"] != "aplicar":
            continue
        nome, id_novo = reg["estilo"], reg["estilo_id"]
        qualificada = "%s:%s" % (reg["ws"], reg["camada"])
        with open(os.path.join(ESTILOS, nome + ".sld"), "w", encoding="utf-8") as fh:
            fh.write(sld(qualificada, nome, [tuple(f) for f in reg["faixas"]]))
        with open(os.path.join(ESTILOS, nome + ".xml"), "w", encoding="utf-8") as fh:
            fh.write(descritor(id_novo, nome))

        lx = caminho_layer_xml(reg["ws"], reg["camada"])
        texto = open(lx, encoding="utf-8").read()
        anterior = re.search(r"<defaultStyle>\s*<id>([^<]*)</id>", texto).group(1)
        reg["estilo_anterior_id"] = anterior
        novo = re.sub(r"(<defaultStyle>\s*<id>)[^<]*(</id>)", r"\g<1>%s\g<2>" % id_novo, texto, count=1)
        if novo == texto:
            raise RuntimeError("nao consegui trocar o defaultStyle em %s" % lx)
        with open(lx, "w", encoding="utf-8") as fh:
            fh.write(novo)
        feitos += 1
    print("estilos aplicados: %d" % feitos)


def reverter(plano: list[dict]) -> None:
    voltas = 0
    for reg in plano:
        if reg["acao"] != "aplicar" or "estilo_anterior_id" not in reg:
            continue
        lx = caminho_layer_xml(reg["ws"], reg["camada"])
        texto = open(lx, encoding="utf-8").read()
        novo = re.sub(r"(<defaultStyle>\s*<id>)[^<]*(</id>)",
                      r"\g<1>%s\g<2>" % reg["estilo_anterior_id"], texto, count=1)
        open(lx, "w", encoding="utf-8").write(novo)
        for ext in (".sld", ".xml"):
            p = os.path.join(ESTILOS, reg["estilo"] + ext)
            if os.path.isfile(p):
                os.remove(p)
        voltas += 1
    print("camadas revertidas: %d" % voltas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--censo")
    ap.add_argument("--plano", required=True)
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--reverter", action="store_true")
    ap.add_argument("--filtro", help="regex: so camadas cujo nome casar")
    args = ap.parse_args()

    if args.reverter:
        reverter(json.load(open(args.plano, encoding="utf-8")))
        return 0

    if os.path.isfile(args.plano) and not args.censo:
        plano = json.load(open(args.plano, encoding="utf-8"))
    else:
        censo = json.load(open(args.censo, encoding="utf-8"))
        if args.filtro:
            censo = [r for r in censo if re.search(args.filtro, r["camada"])]
        print("planejando %d camadas..." % len(censo), flush=True)
        plano = planejar(censo)
        json.dump(plano, open(args.plano, "w", encoding="utf-8"), ensure_ascii=False)

    import collections
    print("\nresumo do plano:")
    for k, n in collections.Counter(
            (r["acao"], r.get("motivo", "")) for r in plano).most_common():
        print("   %-8s %-40s %d" % (k[0], k[1][:40], n))

    if args.aplicar:
        aplicar(plano)
        json.dump(plano, open(args.plano, "w", encoding="utf-8"), ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
