# -*- coding: utf-8 -*-
"""Mede GetMap frio/quente: Int16 + estilo _fixo  x  copia Byte RGB, SO no GeoServer de teste (18081).

Frio = cache de reader do GeoServer de teste zerado (POST /rest/reset) + paginas do .tif/.ovr
tiradas do page cache do SO (posix_fadvise DONTNEED; nao precisa root e nao altera o arquivo).
Quente = mesma requisicao repetida logo depois (mediana de 3).
3 amostras de cada. Cada PNG e decodificado: % de pixel opaco e cor media.
Credencial do GeoServer de teste so por ambiente (GEOSERVER_USER/GEOSERVER_PASSWORD).

Uso: /usr/bin/python3 bench_byte_vs_int16.py
"""
import base64
import io
import json
import os
import statistics
import time
import urllib.request

from PIL import Image

B = "/home/server/Documentos/orquestracao-20260929/wms-byte-ua"
GS = "http://127.0.0.1:18081/geoserver"
HD = "/media/server/HD Backup/RASTER/LANDSAT/224_069/2005/LT05_224069_20051016.tif"
CAMADAS = {
    "orig_hd": [HD, HD + ".ovr"],
    "orig_ssd": [f"{B}/dados/LT05_224069_20051016.tif", f"{B}/dados/LT05_224069_20051016.tif.ovr"],
    "byte_ssd": [f"{B}/dados/LT05_224069_20051016_byte.tif", f"{B}/dados/LT05_224069_20051016_byte.tif.ovr"],
    # mesmas copias com georreferenciamento em EPSG:31982 (CRS que o ArcMap pede): sem reprojecao no render
    "orig_31982": [f"{B}/dados/LT05_224069_20051016_31982.tif", f"{B}/dados/LT05_224069_20051016_31982.tif.ovr"],
    "byte_31982": [f"{B}/dados/LT05_224069_20051016_byte_31982.tif", f"{B}/dados/LT05_224069_20051016_byte_31982.tif.ovr"],
}
# Requisicoes reais do journal do proxy (ArcMap) + extensao inteira
REQS = {
    "arcmap_mais_pedida": "CRS=EPSG:31982&BBOX=337036.2128860127,8613617.277618507,338674.1983845223,8614550.10148995&WIDTH=1108&HEIGHT=631",
    "arcmap_top15": "CRS=EPSG:31982&BBOX=339863.57988869777,8621569.136475507,342458.6184121082,8625120.91024572&WIDTH=613&HEIGHT=839",
    "extensao_inteira": "CRS=EPSG:32622&BBOX=277485,-1542315,513315,-1334385&WIDTH=1024&HEIGHT=903",
}
AUTH = "Basic " + base64.b64encode(
    f"{os.environ['GEOSERVER_USER']}:{os.environ['GEOSERVER_PASSWORD']}".encode()).decode()


def esfriar(arquivos):
    req = urllib.request.Request(f"{GS}/rest/reset", method="POST", headers={"Authorization": AUTH})
    urllib.request.urlopen(req, timeout=60).read()
    for p in arquivos:
        fd = os.open(p, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally:
            os.close(fd)


def getmap(camada, extra):
    url = (f"{GS}/staging/wms?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&{extra}&LAYERS=staging:{camada}"
           "&STYLES=&EXCEPTIONS=XML&FORMAT=image/png&BGCOLOR=0xFEFFFF&TRANSPARENT=TRUE")
    t = time.perf_counter()
    corpo = urllib.request.urlopen(url, timeout=120).read()
    dt = time.perf_counter() - t
    try:
        im = Image.open(io.BytesIO(corpo)).convert("RGBA")
    except Exception:
        return dt, {"erro": corpo[:300].decode("utf-8", "replace")}, corpo
    px = [p for p in im.getdata() if p[3] > 0]
    pct = 100.0 * len(px) / (im.size[0] * im.size[1])
    media = [round(sum(p[i] for p in px) / len(px), 1) for i in range(3)] if px else None
    return dt, {"opaco_pct": round(pct, 2), "rgb_medio": media, "bytes": len(corpo)}, corpo


def main():
    res = []
    for nome_req, extra in REQS.items():
        for amostra in range(1, 4):
            for camada, arqs in CAMADAS.items():
                esfriar(arqs)
                frio, info, corpo = getmap(camada, extra)
                quentes = [getmap(camada, extra)[0] for _ in range(3)]
                if amostra == 1:
                    open(f"{B}/png/{nome_req}_{camada}.png", "wb").write(corpo)
                linha = {"req": nome_req, "amostra": amostra, "camada": camada, "frio_s": round(frio, 3),
                         "quente_mediana_s": round(statistics.median(quentes), 3), **info}
                print(json.dumps(linha, ensure_ascii=False), flush=True)
                res.append(linha)
    json.dump(res, open(f"{B}/bench-results.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
