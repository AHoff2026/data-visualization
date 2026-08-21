#!/usr/bin/env python3
"""Remove one dimension value from a dataset, rewriting the payload and
re-indexing every series. Use only where the values are duplicated elsewhere."""
import json, gzip, pathlib, sys
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"

def run(slug, dim_id, code):
    d = ROOT/"site/data/flows"/slug
    mp = d/"meta.json"
    m = json.loads(mp.read_text())
    di = next((i for i, x in enumerate(m["dims"]) if x["id"] == dim_id), None)
    if di is None: return f"{slug}: no {dim_id}"
    dim = m["dims"][di]
    if code not in dim["ids"]: return f"{slug}: {code} already absent"
    drop = dim["ids"].index(code)

    if m["layout"] == "single":
        recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
    else:
        recs = []
        for info in (m.get("parts") or {}).values():
            f = d/"parts"/info["file"]
            if f.exists(): recs += json.loads(gzip.decompress(f.read_bytes()))
    before = len(recs)
    recs = [r for r in recs if r["k"][di] != drop]
    keep = [j for j in range(len(dim["ids"])) if j != drop]
    remap = {old: new for new, old in enumerate(keep)}
    for r in recs: r["k"][di] = remap[r["k"][di]]
    dim["ids"] = [dim["ids"][j] for j in keep]
    dim["names"] = [dim["names"][j] for j in keep]
    m["n_series"] = len(recs); m["n_obs"] = sum(len(r["v"]) for r in recs)

    if m["layout"] == "single":
        (d/"all.json.gz").write_bytes(gzip.compress(
            json.dumps(recs, separators=(",", ":")).encode(), 6))
    else:
        ai = next(i for i, x in enumerate(m["dims"]) if x["id"] == m["area_dim"])
        codes = m["dims"][ai]["ids"]
        by = defaultdict(list)
        for r in recs: by[codes[r["k"][ai]]].append(r)
        parts = {}
        for c, rs in by.items():
            fn = (m.get("parts") or {}).get(c, {}).get("file") or (c + ".json.gz")
            blob = gzip.compress(json.dumps(rs, separators=(",", ":")).encode(), 6)
            (d/"parts"/fn).write_bytes(blob)
            parts[c] = {"file": fn, "n": len(rs), "bytes": len(blob)}
        m["parts"] = parts
    mp.write_text(json.dumps(m, separators=(",", ":")))
    return f"{slug}: dropped {dim_id}={code}, {before-len(recs)} series removed, {len(recs)} remain"

if __name__ == "__main__":
    print(run(*sys.argv[1:4]))
