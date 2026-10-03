# -*- coding: utf-8 -*-
"""Confere se a janela SUL da cena tem dado de verdade no arquivo.

Uso: janela.py <tif> [x y w h]   (padrao = janela 'sul' do comparativo)
Le com a API do GDAL e conta pixel != 0 (0 = NoData da cena).
"""
import sys

from osgeo import gdal

gdal.UseExceptions()

TIF = sys.argv[1]
ds = gdal.Open(TIF)
gt = ds.GetGeoTransform()
if len(sys.argv) > 5:
    px, py, pw, ph = (int(v) for v in sys.argv[2:6])
else:
    px, py, pw, ph = 24367, 53078, 512, 512  # sul: x=330000, y=8545000
x = gt[0] + px * gt[1] + py * gt[2]
y = gt[3] + px * gt[4] + py * gt[5]
print(f"{TIF.split('/')[-1]}: size={ds.RasterXSize}x{ds.RasterYSize} "
      f"orig=({gt[0]:.0f},{gt[3]:.0f}) px={gt[1]}x{gt[5]} "
      f"janela px({px},{py} {pw}x{ph}) = xy({x:.0f},{y:.0f})")
for b in range(1, ds.RasterCount + 1):
    arr = ds.GetRasterBand(b).ReadAsArray(px, py, pw, ph)
    nz = int((arr != 0).sum())
    tot = arr.size
    print(f"  banda {b}: dado={100*nz/tot:6.2f}%  min={arr.min():6d} max={arr.max():6d} "
          f"media={arr.mean():9.2f}")