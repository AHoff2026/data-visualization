#!/usr/bin/env python3
"""Find series that are identical to one another.

Two lines on a chart that carry the same numbers are worse than useless: they
imply agreement between distinct things. This finds every pair of areas whose
published values coincide across a large share of their overlap.
"""
import json, gzip, pathlib, itertools, sys
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
THRESH = 0.90     # share of overlapping observations that must match to flag
MIN_OBS = 40

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

findings = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    ai = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "REF_AREA"), None)
    if ai is None: continue
    ids, names = meta["dims"][ai]["ids"], meta["dims"][ai]["names"]
    recs = load(mp, meta)
    by = defaultdict(dict)
    for r in recs:
        key = tuple(v for i, v in enumerate(r["k"]) if i != ai)
        by[key][r["k"][ai]] = dict(zip(r["t"], r["v"]))
    pair = defaultdict(lambda: [0, 0])
    for key, d2 in by.items():
        for a, b in itertools.combinations(sorted(d2), 2):
            common = set(d2[a]) & set(d2[b])
            if not common: continue
            same = sum(1 for t in common if abs(d2[a][t] - d2[b][t]) < 1e-9)
            p = pair[(a, b)]
            p[0] += same; p[1] += len(common)
    for (a, b), (same, tot) in pair.items():
        if tot >= MIN_OBS and same / tot >= THRESH:
            findings.append({
                "slug": meta["slug"], "flow": meta["name"],
                "a": ids[a], "a_name": names[a], "b": ids[b], "b_name": names[b],
                "identical": same, "overlap": tot, "share": round(same / tot, 3),
            })

findings.sort(key=lambda f: -f["share"])
(ROOT/"tests/duplicates.json").write_text(json.dumps(findings, indent=1))
print(f"identical-series pairs found: {len(findings)}\n")
for f in findings[:30]:
    print(f'  {f["share"]*100:5.1f}%  {f["a_name"][:30]:30} = {f["b_name"][:30]:30}  {f["flow"][:34]}')
sys.exit(0)
