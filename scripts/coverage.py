#!/usr/bin/env python3
"""Record, per dataset, which of the sample countries it actually covers, so a
gap is visible on the page instead of being discovered by clicking."""
import json, gzip, pathlib
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
cat = json.loads((ROOT/"site/data/catalog.json").read_text())
SAMPLE = cat["sample_countries"]

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

by_slug = {f["slug"]: f for f in cat["flows"]}
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    ai = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "REF_AREA"), None)
    if ai is None: continue
    ids = meta["dims"][ai]["ids"]
    obs = defaultdict(int); span = {}
    for r in load(mp, meta):
        code = ids[r["k"][ai]]
        obs[code] += len(r["v"])
        if r["t"]:
            lo, hi = meta["periods"][r["t"][0]], meta["periods"][r["t"][-1]]
            cur = span.get(code)
            span[code] = (min(cur[0], lo), max(cur[1], hi)) if cur else (lo, hi)
    covered = [c for c in SAMPLE if obs.get(c, 0) > 0]
    missing = [c for c in SAMPLE if obs.get(c, 0) == 0]
    meta["coverage"] = {
        "sample_covered": covered,
        "sample_missing": missing,
        "sample_span": {c: span[c] for c in covered if c in span},
    }
    mp.write_text(json.dumps(meta, separators=(",", ":")))
    f = by_slug.get(meta["slug"])
    if f: f["sample_missing"] = missing
(ROOT/"site/data/catalog.json").write_text(json.dumps(cat, separators=(",", ":")))
n = sum(1 for f in cat["flows"] if f.get("sample_missing"))
print(f"datasets with a sample-country gap: {n} of {len(cat['flows'])}")
