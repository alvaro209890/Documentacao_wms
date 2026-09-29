# -*- coding: utf-8 -*-
"""So leitura: para cada GeoTIFF referenciado por coveragestore.xml do workspace cbers,
compara o fim do ULTIMO tile (offset+size lido do cabecalho TIFF) com o tamanho do
arquivo. Fim alem do arquivo = TIFF truncado (render falha nessa regiao).

Le so o cabecalho/IFD (GDAL metadata BLOCK_OFFSET_*), nao os pixels (~1 min p/ 743 tifs).
Uso (no servidor): /usr/bin/python3 checar_tiff_truncado.py [saida.json]   (padrao /tmp/truncados.json)
       arquivo avulso: /usr/bin/python3 checar_tiff_truncado.py --arquivo <a.tif> [b.tif ...]
                       (saida em /tmp/truncados_arquivo.json)
Achado de 29/09/2026: 1 truncado (213_129 20250813 L4 C342 PAN), 5 sem overview.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import urllib.parse

from osgeo import gdal

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")
AQUI = os.path.dirname(os.path.abspath(__file__))
WS = "/home/server/geoserver_data/workspaces/cbers"


def main() -> int:
    alvos = {}
    # --arquivo <tif> [...]: checa so os arquivos dados (ex.: copia em staging), sem varrer o workspace
    if len(sys.argv) > 2 and sys.argv[1] == "--arquivo":
        for p in sys.argv[2:]:
            alvos[os.path.abspath(p)] = os.path.basename(p)
        sys.argv = sys.argv[:1] + ["/tmp/truncados_arquivo.json"]
    for cs in ([] if alvos else glob.glob(os.path.join(WS, "*", "coveragestore.xml"))):
        txt = open(cs, encoding="utf-8").read()
        m = re.search(r"<url>([^<]+)</url>", txt)
        if not m:
            continue
        p = urllib.parse.unquote(m.group(1).replace("file:", "", 1))
        if p.lower().endswith((".tif", ".tiff")):
            alvos[p] = os.path.basename(os.path.dirname(cs))
    res = {"verificados": 0, "sem_arquivo": [], "truncados": [], "erro_abrir": [],
           "sem_overview": 0}
    for p, store in sorted(alvos.items()):
        if not os.path.isfile(p):
            res["sem_arquivo"].append(store)
            continue
        try:
            ds = gdal.Open(p)
            b = ds.GetRasterBand(1)
            bx, by = b.GetBlockSize()
            nx = (ds.RasterXSize + bx - 1) // bx
            ny = (ds.RasterYSize + by - 1) // by
            fim = 0
            for tx, ty in ((nx - 1, ny - 1), (0, ny - 1), (nx - 1, 0)):
                o = b.GetMetadataItem("BLOCK_OFFSET_%d_%d" % (tx, ty), "TIFF")
                s = b.GetMetadataItem("BLOCK_SIZE_%d_%d" % (tx, ty), "TIFF")
                if o and s:
                    fim = max(fim, int(o) + int(s))
            tam = os.path.getsize(p)
            res["verificados"] += 1
            if b.GetOverviewCount() == 0:
                res["sem_overview"] += 1
            if fim > tam:
                res["truncados"].append({"store": store, "arquivo": p, "tamanho": tam,
                                         "fim_ultimo_tile": fim, "faltam_bytes": fim - tam,
                                         "overviews": b.GetOverviewCount()})
        except Exception as e:
            res["erro_abrir"].append({"store": store, "erro": str(e)[:120]})
    saida = sys.argv[1] if len(sys.argv) > 1 else "/tmp/truncados.json"
    json.dump(res, open(saida, "w"), indent=2, ensure_ascii=False)
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in res.items()}))
    for t in res["truncados"]:
        print("TRUNCADO", t["store"], t["faltam_bytes"], "overviews=%d" % t["overviews"])
    for t in res["erro_abrir"]:
        print("ERRO", t)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
