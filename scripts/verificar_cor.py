# -*- coding: utf-8 -*-
"""Mede se a cor de uma camada raster depende do BBOX pedido.

Pede a cena inteira, recorta dela um pedaco, e pede esse mesmo pedaco
separadamente. Se o realce for absoluto, as duas versoes do MESMO chao tem
que ter a mesma media RGB. Diferenca alta = realce calculado por requisicao.

    python3 verificar_cor.py [--n 12] [--camadas nome1 nome2 ...]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import urllib.parse
import urllib.request

import numpy as np
from PIL import Image
from osgeo import gdal

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

BASE = "http://localhost:8081/geoserver/wms"
RAIZ = "/home/server/geoserver_data/workspaces"
LIMITE = 3.0   # niveis RGB; acima disso a cor depende do recorte


def srs_da_camada(ws: str, camada: str) -> str | None:
    for store in os.listdir(os.path.join(RAIZ, ws)):
        p = os.path.join(RAIZ, ws, store, camada, "coverage.xml")
        if os.path.isfile(p):
            m = re.search(r"<srs>([^<]*)</srs>", open(p, encoding="utf-8", errors="replace").read())
            return m.group(1) if m else None
    return None


def getmap(camada_q: str, srs: str, bbox, w: int, h: int) -> Image.Image:
    q = {"service": "WMS", "version": "1.1.1", "request": "GetMap", "layers": camada_q,
         "styles": "", "srs": srs, "bbox": ",".join("%.4f" % v for v in bbox),
         "width": w, "height": h, "format": "image/png"}
    d = urllib.request.urlopen(BASE + "?" + urllib.parse.urlencode(q), timeout=300).read()
    if d[:4] != b"\x89PNG":
        raise RuntimeError(d.decode("utf-8", "replace")[:200])
    return Image.open(io.BytesIO(d)).convert("RGB")


def medir(reg: dict) -> tuple[float, str] | None:
    srs = srs_da_camada(reg["ws"], reg["camada"])
    if not srs:
        return None
    ds = gdal.Open(reg.get("amostra") or reg["caminho"])
    gt = ds.GetGeoTransform()
    x0, y1 = gt[0], gt[3]
    x1 = x0 + gt[1] * ds.RasterXSize
    y0 = y1 + gt[5] * ds.RasterYSize
    w, h = x1 - x0, y1 - y0
    grande_bbox = (x0, y0, x1, y1)
    dentro = (x0 + 0.40 * w, y0 + 0.40 * h, x0 + 0.52 * w, y0 + 0.52 * h)
    q = "%s:%s" % (reg["ws"], reg["camada"])

    grande = getmap(q, srs, grande_bbox, 900, max(50, int(900 * h / w)))
    W, H = grande.size
    rec = grande.crop((int((dentro[0] - x0) / w * W), int((y1 - dentro[3]) / h * H),
                       int((dentro[2] - x0) / w * W), int((y1 - dentro[1]) / h * H)))
    pro = getmap(q, srs, dentro, 900, 700).resize(rec.size)
    m1 = np.asarray(rec, float).reshape(-1, 3).mean(0)
    m2 = np.asarray(pro, float).reshape(-1, 3).mean(0)
    dif = float(np.abs(m2 - m1).max())
    return dif, "%s -> %s" % (np.round(m1, 1), np.round(m2, 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--censo", default="/tmp/censo.json")
    ap.add_argument("--n", type=int, default=12, help="amostras por tipo de dado")
    ap.add_argument("--camadas", nargs="*")
    args = ap.parse_args()

    censo = json.load(open(args.censo, encoding="utf-8"))
    if args.camadas:
        alvos = [r for r in censo if r["camada"] in args.camadas]
    else:
        alvos, por_tipo = [], {}
        for r in censo:
            t = r.get("dtype")
            if not t:
                continue
            por_tipo.setdefault(t, [])
            if len(por_tipo[t]) < args.n:
                por_tipo[t].append(r)
                alvos.append(r)

    piores = []
    for r in alvos:
        try:
            resultado = medir(r)
        except Exception as e:
            print("  %-8s %-52s ERRO %s" % (r.get("dtype"), r["camada"][:52], str(e)[:60]))
            continue
        if not resultado:
            continue
        dif, detalhe = resultado
        marca = "OK " if dif <= LIMITE else "!! "
        print("%s %-8s %-52s dif_max=%5.1f  %s" % (marca, r.get("dtype"), r["camada"][:52], dif, detalhe))
        piores.append((dif, r["camada"], r.get("dtype")))

    if piores:
        ruins = [p for p in piores if p[0] > LIMITE]
        print("\ncamadas medidas: %d | acima de %.1f niveis: %d" % (len(piores), LIMITE, len(ruins)))
        for dif, nome, t in sorted(ruins, reverse=True)[:10]:
            print("   %5.1f  %-8s %s" % (dif, t, nome))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
