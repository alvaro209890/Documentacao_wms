# -*- coding: utf-8 -*-
"""Gera COPIA Byte (RGB) de uma cena Landsat Int16 com o realce do estilo _fixo gravado no pixel.

Mapeamento por banda: valor -> 1 + (v - min) * 254 / (max - min), cortado em 1..255.
0 fica reservado para nodata e so e gravado onde o original e nodata (-9999).
(gdal_translate -scale NAO serve: corta no limite do tipo, entao pixel escuro vira 0 = nodata.)

Uso: /usr/bin/python3 gerar_copia_byte.py <entrada.tif> <saida.tif> min1 max1 min2 max2 min3 max3
Depois: gdaladdo -r average -ro --config COMPRESS_OVERVIEW LZW <saida.tif> 2 4 8 16 32
So escreve <saida.tif>; a entrada e aberta so para leitura.
"""
import sys

import numpy as np
from osgeo import gdal

gdal.UseExceptions()


def main() -> int:
    ent, sai = sys.argv[1], sys.argv[2]
    lim = [float(x) for x in sys.argv[3:9]]
    src = gdal.Open(ent)
    drv = gdal.GetDriverByName("GTiff")
    dst = drv.Create(sai, src.RasterXSize, src.RasterYSize, 3, gdal.GDT_Byte,
                     ["TILED=YES", "BLOCKXSIZE=128", "BLOCKYSIZE=128",
                      "COMPRESS=LZW", "PHOTOMETRIC=RGB"])
    dst.SetGeoTransform(src.GetGeoTransform())
    dst.SetProjection(src.GetProjection())
    for i in range(3):
        bi = src.GetRasterBand(i + 1)
        nd = bi.GetNoDataValue()
        a = bi.ReadAsArray().astype("float32")
        lo, hi = lim[2 * i], lim[2 * i + 1]
        out = np.clip(np.rint(1 + (a - lo) * 254.0 / (hi - lo)), 1, 255).astype("uint8")
        if nd is not None:
            out[a == nd] = 0
        bo = dst.GetRasterBand(i + 1)
        bo.WriteArray(out)
        bo.SetNoDataValue(0)
        print("banda %d: min=%g max=%g nodata_orig=%d" % (i + 1, lo, hi, int((a == nd).sum()) if nd is not None else 0))
    dst.FlushCache()
    dst = None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
