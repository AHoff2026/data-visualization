#!/usr/bin/env python3
"""Earnings dispersion ships the ratio twice.

AGGREGATION_OPERATION already says which ratio it is — 9/1, 5/1, 9/5 — and
UNIT_MEASURE then restates that ratio's denominator as "Factor of decile 1" or
"Factor of decile 5". The unit carries no information the ratio does not, so it
collapses to a single value and the ratio gets names a reader can act on.
"""
import gzip, json, pathlib

ROOT = pathlib.Path.home()/"Documents/data-visualization"
d = ROOT/"site/data/flows/OECD.ELS.SAE__DEC_I"
mp = d/"meta.json"
m = json.loads(mp.read_text())
idx = {x["id"]: i for i, x in enumerate(m["dims"])}
recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))

ui = idx["UNIT_MEASURE"]
unit = m["dims"][ui]
if len(unit["ids"]) > 1:
    unit["ids"], unit["names"] = ["RATIO"], ["Ratio"]
    for r in recs: r["k"][ui] = 0

ai = idx.get("AGGREGATION_OPERATION")
if ai is not None:
    LBL = {"D9_1": "90th to 10th percentile (D9/D1)",
           "D5_1": "50th to 10th percentile (D5/D1)",
           "D9_5": "90th to 50th percentile (D9/D5)"}
    agg = m["dims"][ai]
    agg["name"] = "Ratio"
    agg["names"] = [LBL.get(c, n) for c, n in zip(agg["ids"], agg["names"])]

mp.write_text(json.dumps(m, separators=(",", ":")))
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(recs, separators=(",", ":")).encode(), 6))
print("units collapsed; ratio relabelled:", m["dims"][ai]["names"] if ai is not None else "-")
