#!/usr/bin/env python3
"""Find year-on-year jumps large enough to suggest a break in series.

A definitional change looks like a real change on a chart. This flags where a
single step dwarfs the surrounding variation, so the page can warn rather than
let a reader read a redefinition as history.
"""
import json, gzip, pathlib, statistics
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
MIN_POINTS = 12
K = 8.0        # a step this many times the typical step is not ordinary movement

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
    per = meta["periods"]
    hits = defaultdict(int); worst = ("", 0, 0)
    n_series = 0
    for r in load(mp, meta):
        if len(r["v"]) < MIN_POINTS: continue
        n_series += 1
        steps = [abs(r["v"][i] - r["v"][i-1]) for i in range(1, len(r["v"]))]
        typical = statistics.median(steps)
        if typical <= 0: continue
        for i, st in enumerate(steps, start=1):
            if st > K * typical and st > 1e-9:
                yr = per[r["t"][i]]
                hits[yr] += 1
                if st / typical > worst[2]:
                    area = meta["dims"][ai]["ids"][r["k"][ai]] if ai is not None else "?"
                    worst = (f"{area} {yr}", round(st, 2), round(st / typical, 1))
    if hits:
        top = sorted(hits.items(), key=lambda x: -x[1])[:3]
        rows.append((meta["name"], n_series, sum(hits.values()), top, worst))

rows.sort(key=lambda r: -(r[2] / max(r[1], 1)))
print(f"datasets with abrupt steps: {len(rows)}\n")
print(f"{'jumps':>6} {'series':>7}  years most affected            dataset")
for name, ns, nh, top, worst in rows[:16]:
    yrs = ", ".join(f"{y}({c})" for y, c in top)
    print(f"{nh:6} {ns:7}  {yrs[:30]:30} {name[:38]}")
