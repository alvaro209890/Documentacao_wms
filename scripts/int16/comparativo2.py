# -*- coding: utf-8 -*-
"""Comparativo truncado x candidato no GeoServer de teste (18081), ponto a ponto.

Mede, para cada versao da cena, em pontos ESCOLHIDOS DENTRO DA AREA COM DADO
(ver grade_trunc.txt / grade_cand.txt), http, tempo, bytes, % opaco e se saiu
PNG com dado. Versoes:
  TRUNC = .tif de producao hoje (truncado, sem .ovr)
  CAND  = candidato do INPE (completo, com .ovr)
  NOOVR = mesmo .tif do CAND sem o .ovr (isola o efeito do overview)
  IRMA  = cena Byte irma de 8 m, mesma data (sanidade)

Uso: comparativo2.py <saida_dir> <gs_base>
"""
import json
import os
import subprocess
import sys
import time

PCT = "/home/server/Documentos/orquestracao-20260929/int16-redownload/pct_opaco.py"
VERS = [("TRUNC", "cbers:INT16_TRUNC"), ("CAND", "cbers:INT16_CAND"),
        ("NOOVR", "cbers:INT16_NOOVR"), ("IRMA", "cbers:BYTE_IRMA")]

# EPSG:32722 (projetado -> x,y). Native bbox 281266..393570 x 8535736..8651156.
# Escolhidos na faixa que a grade mostrou ter dado nas DUAS versoes:
# x 300000-390000, y 8600000 (norte), 8560000 e 8550000 (meio/sul, dentro da
# borda da orbita) e a cena inteira (8510000..8651156, que usa overview).
PONTOS = [
    ("norte",     300000, 8600000, 302000, 8602000),
    ("meio",      300000, 8573000, 302000, 8575000),
    ("sul_dado",  300000, 8550000, 302000, 8552000),
    ("sul_fim",   300000, 8560000, 302000, 8562000),
    ("leste",     380000, 8560000, 382000, 8562000),
    ("geral",     281266, 8535736, 393570, 8651156),  # cena toda -> overview
]
REPETICOES = {True: 1, False: 3}


def getmap(base, layer, bbox, out, w=256, h=256):
    url = (f"{base}/cbers/wms?service=WMS&version=1.3.0&request=GetMap"
           f"&format=image/png&transparent=true&styles=&layers={layer}"
           f"&crs=EPSG:32722&bbox={bbox}&width={w}&height={h}")
    t0 = time.time()
    r = subprocess.run(["curl", "-s", "-m", "600", "-o", out, "-w",
                        "%{http_code} %{time_total} %{size_download}", url],
                       capture_output=True, text=True)
    wall = time.time() - t0
    code, tt, size = (r.stdout.split() + ["", "", "0"])[:3]
    p = subprocess.run(["/usr/bin/python3", PCT, out], capture_output=True, text=True)
    return {"http": code, "curl_s": float(tt or 0), "wall_s": round(wall, 2),
            "bytes": int(size or 0), "pct": p.stdout.strip(),
            "png_com_dado": p.returncode == 0}


def main():
    saida, base = sys.argv[1], sys.argv[2]
    os.makedirs(saida, exist_ok=True)
    rows = []
    for nome, x0, y0, x1, y1 in PONTOS:
        bb = f"{x0},{y0},{x1},{y1}"
        geral = nome == "geral"
        for v, camada in VERS:
            tempos, tam, dados = [], 0, 0
            for r in range(REPETICOES[geral]):
                out = os.path.join(saida, f"{v}_{nome}_{r}.png")
                m = getmap(base, camada, bb, out)
                tempos.append(m["curl_s"])
                tam, dados = m["bytes"], dados + (1 if m["png_com_dado"] else 0)
                if r == 0:
                    rows.append({"versao": v, "ponto": nome, "camada": camada,
                                 "bbox": bb, **m})
            u = rows[-1]
            u["media_s"] = round(sum(tempos) / len(tempos), 2)
            u["n_com_dado"] = f"{dados}/{REPETICOES[geral]}"
            print(f"{nome:9s} {v:6s} http={u['http']:>3s} {u['media_s']:8.2f}s "
                  f"{tam/1024:8.1f}KB dado={u['n_com_dado']:>3s}  {u['pct'][:44]}",
                  flush=True)
    with open(os.path.join(saida, "comparativo2.json"), "w") as f:
        json.dump(rows, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())