# -*- coding: utf-8 -*-
"""Mapa de dado por grade: onde a cena tem pixel != 0 (0 = NoData).

Uso: grade.py <tif> <n_linhas_x_colunas> [passo_px]
Mostra uma matriz ASCII: '#' dado cheio, '+' parcial, '.' so nodata, 'E' erro de leitura.
Compara TRUNC x CAND na MESMA grade de coordenadas geograficas.
"""
import sys

from osgeo import gdal

gdal.UseExceptions()
gdal.PushErrorHandler("CPLQuietErrorHandler")

TIF = sys.argv[1]
N = int(sys.argv[2]) if len(sys.argv) > 2 else 36
STEP_PX = int(sys.argv[3]) if len(sys.argv) > 3 else 1404  # ~2,8 km na cena PAN

ds = gdal.Open(TIF)
gt = ds.GetGeoTransform()
X, Y = ds.RasterXSize, ds.RasterYSize
bx, by = STEP_PX, STEP_PX
linhas, colunas = Y // by, X // bx
print(f"{TIF.split('/')[-1]}: {X}x{Y} grade {colunas}x{linhas} bloco {bx}x{by}px "
      f"({bx*abs(gt[1])/1000:.1f}x{by*abs(gt[5])/1000:.1f} km)")
erros = 0
print("     " + "".join(str(i % 10) for i in range(colunas)))
for r in range(linhas):
    linha = ""
    for c in range(colunas):
        x, y = c * bx, r * by
        if x + bx > X or y + by > Y:
            linha += " "
            continue
        try:
            tot = 0
            dado = 0
            for b in range(1, ds.RasterCount + 1):
                a = ds.GetRasterBand(b).ReadAsArray(x, y, min(bx, X - x), min(by, Y - y))
                tot += a.size
                dado += int((a != 0).sum())
            f = 100.0 * dado / tot
            linha += "#" if f > 95 else ("+" if f > 5 else ".")
        except RuntimeError:
            linha += "E"
            erros += 1
    print(f"{r:4d} {linha}")
print(f"erros de leitura: {erros}")