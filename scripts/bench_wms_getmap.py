#!/usr/bin/env python3
"""Benchmark read-only do WMS: GetMap/GetCapabilities em 8081, 8082 e wms.cursar.space.

Usa o GetMap real mais recente de cada camada (extraído do journal do proxy),
3 rodadas; em cada rodada a ordem é 8081 -> 8082 -> público. Não altera nada.
"""
import io
import json
import subprocess
import time
import uuid

from PIL import Image

ENDPOINTS = {
    "8081": "http://127.0.0.1:8081",
    "8082": "http://127.0.0.1:8082",
    "publico": "https://wms.cursar.space",
}
CURL_FMT = "%{http_code}|%{time_starttransfer}|%{time_total}|%{size_download}|%{content_type}"
UA = "Mozilla/5.0 (hermes-wms-bench)"


def curl(url: str) -> dict:
    out = f"/tmp/wmsbench_{uuid.uuid4().hex}"
    hdr = out + ".h"
    p = subprocess.run(
        ["curl", "-s", "--max-time", "120", "-A", UA, "-D", hdr, "-o", out, "-w", CURL_FMT, url],
        capture_output=True, text=True,
    )
    code, ttfb, total, size, ctype = (p.stdout.split("|") + ["", "", "", "", ""])[:5]
    res = {"code": code, "ttfb": float(ttfb or 0), "total": float(total or 0),
           "bytes": int(float(size or 0)), "ctype": ctype}
    try:
        h = open(hdr, errors="replace").read().lower()
        for line in h.splitlines():
            if line.startswith("cf-cache-status:"):
                res["cf_cache"] = line.split(":", 1)[1].strip()
    except OSError:
        pass
    try:
        data = open(out, "rb").read()
        if ctype.startswith("image/"):
            im = Image.open(io.BytesIO(data)).convert("RGBA")
            px = list(im.getdata())
            bg = (0xFE, 0xFF, 0xFF)
            vis = sum(1 for r, g, b, a in px if a > 0 and (r, g, b) != bg)
            res["pct_com_dado"] = round(100 * vis / len(px), 1)
        elif data:
            res["erro"] = data[:200].decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        res["erro_decode"] = str(exc)
    subprocess.run(["rm", "-f", out, hdr])
    return res


def main() -> None:
    top = json.load(open("top15.json"))
    results = {"inicio": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "getmap": [], "caps": []}

    caps_q = "/geoserver/cbers/wms?service=WMS&request=GetCapabilities&version=1.3.0"
    for rnd in range(1, 4):
        for ep, base in ENDPOINTS.items():
            r = curl(base + caps_q)
            r.update(endpoint=ep, rodada=rnd)
            results["caps"].append(r)
            print("caps", ep, rnd, r["code"], round(r["total"], 2), r["bytes"], flush=True)
        time.sleep(2)

    for o in top:
        for rnd in range(1, 4):
            for ep, base in ENDPOINTS.items():
                url = base + o["path"] + "?" + o["query"]
                if ep == "publico":
                    # cache-buster para medir a origem e não o edge do Cloudflare
                    url += f"&_bench={uuid.uuid4().hex[:8]}"
                r = curl(url)
                r.update(endpoint=ep, rodada=rnd, layer=o["layer"])
                results["getmap"].append(r)
                print(o["layer"][:45], ep, rnd, r["code"], round(r["total"], 2),
                      r.get("pct_com_dado"), r.get("cf_cache", ""), r.get("erro", "")[:80], flush=True)
        json.dump(results, open("bench-results.json", "w"), indent=1)

    results["fim"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    json.dump(results, open("bench-results.json", "w"), indent=1)


if __name__ == "__main__":
    main()
