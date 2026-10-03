# -*- coding: utf-8 -*-
"""Imprime '% de pixel opaco' de um PNG (ou mostra o XML, se o WMS devolveu erro).

Uso: /usr/bin/python3 pct_opaco.py arquivo.png
Sai com codigo 0 se PNG com dado (> 0,5% opaco), 1 se PNG vazio, 2 se nao e PNG.
"""
import sys

from PIL import Image


def main() -> int:
    p = sys.argv[1]
    try:
        im = Image.open(p).convert("RGBA")
    except Exception:
        corpo = open(p, "rb").read(400).decode("utf-8", "replace")
        print("NAO-PNG: " + " ".join(corpo.split())[:300])
        return 2
    h = im.getchannel("A").histogram()
    pct = 100.0 * (1 - h[0] / sum(h))
    print("PNG %dx%d opaco=%.2f%%" % (im.size[0], im.size[1], pct))
    return 0 if pct > 0.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
