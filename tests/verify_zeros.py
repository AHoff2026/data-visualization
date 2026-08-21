#!/usr/bin/env python3
"""Find series that are entirely zero.

A zero can be real (nobody in a category) but a series that is zero at every
observation, in a measure where zero is impossible — hours worked, earnings, an
average duration — is a placeholder published as data. Plotted, it is a flat
line at the axis floor that also crushes the scale for every other country.
"""
import json, gzip, pathlib
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

def load(mp, meta):
    d = mp.parent
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for info in (meta.get("parts") or {}).values():
        f = d/"parts"/info["file"]
        if f.exists(): out += json.loads(gzip.decompress(f.read_bytes()))
    return out

rows = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    ai = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "REF_AREA"), None)
    ui = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "UNIT_MEASURE"), None)
    recs = load(mp, meta)
    if not recs: continue
    allzero = [r for r in recs if r["v"] and all(v == 0 for v in r["v"])]
    if not allzero: continue
    areas = defaultdict(int)
    for r in allzero:
        if ai is not None: areas[meta["dims"][ai]["ids"][r["k"][ai]]] += 1
    units = set()
    for r in allzero:
        if ui is not None: units.add(meta["dims"][ui]["names"][r["k"][ui]])
    rows.append({
        "slug": meta["slug"], "flow": meta["name"],
        "zero_series": len(allzero), "total_series": len(recs),
        "share": round(len(allzero)/len(recs), 3),
        "areas": sorted(areas, key=lambda a: -areas[a])[:8],
        "units": sorted(units)[:3],
    })

rows.sort(key=lambda r: -r["share"])
(ROOT/"tests/zeros.json").write_text(json.dumps(rows, indent=1))
print(f"datasets containing all-zero series: {len(rows)}\n")
for r in rows:
    print(f'  {r["share"]*100:5.1f}%  {r["zero_series"]:6}/{r["total_series"]:6}  {r["flow"][:44]:44} {r["areas"][:5]}')
    print(f'{"":16}units: {r["units"]}')
