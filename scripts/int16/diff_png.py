# -*- coding: utf-8 -*-
"""Compara 2 PNGs do mesmo ponto: diferenca pixel a pixel e cores medias.

Uso: diff_png.py a.png b.png [rotulo]
"""
import sys

import numpy as np
from PIL import Image


def carrega(p):
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im).astype(np.int16)
    return a


def main():
    a, b = carrega(sys.argv[1]), carrega(sys.argv[2])
    rot = sys.argv[3] if len(sys.argv) > 3 else ""
    if a.shape != b.shape:
        print(f"{rot}: FORMAS DIFERENTES {a.shape} vs {b.shape}")
        return 1
    op_a, op_b = a[..., 3] > 0, b[..., 3] > 0
    rgb_a, rgb_b = a[..., :3], b[..., :3]
    print(f"{rot}: {a.shape[1]}x{a.shape[0]}  opaco A={100*op_a.mean():.2f}% "
          f"B={100*op_b.mean():.2f}%")
    for nome, c in (("A", rgb_a), ("B", rgb_b)):
        m = c[op_a if nome == "A" else op_b]
        print(f"   cor media {nome}: R={m[:,0].mean():6.1f} G={m[:,1].mean():6.1f} "
              f"B={m[:,2].mean():6.1f}")
    cinza_a = np.abs(rgb_a[..., 0].astype(int) - rgb_a[..., 2]) < 3
    cinza_b = np.abs(rgb_b[..., 0].astype(int) - rgb_b[..., 2]) < 3
    com_a = 100 * cinza_a[op_a].mean() if op_a.any() else 0
    com_b = 100 * cinza_b[op_b].mean() if op_b.any() else 0
    print(f"   pixel cinza (R≈B): A={com_a:.1f}%  B={com_b:.1f}%")
    if op_a.any() and op_b.any():
        d = np.abs(rgb_a[op_a & op_b] - rgb_b[op_a & op_b])
        print(f"   |A-B| onde ambos tem dado: media={d.mean():.2f} max={d.max()} "
              f"(px comparados={(op_a & op_b).sum()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())