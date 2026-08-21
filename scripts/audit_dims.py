#!/usr/bin/env python3
"""Find dial pairs that are not independent axes.

Two dials are only worth having separately if their combinations are mostly
populated. When one dial's value determines the other's — "Part-time
employment" only ever appears with Working time = Part-time — the grid is empty
by construction and the reader hunts for combinations that cannot exist.

Reports, per dataset and dial pair:
  fill      share of the value grid that actually carries data
  A->B      share of A's values that pin B to a single value
  B->A      the same in reverse
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

findings = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    dims = meta["dims"]
    hidden = set((meta.get("hidden_dims") or {}).keys())
    idxs = [i for i, d in enumerate(dims)
            if len(d["ids"]) > 1 and d["id"] not in ("REF_AREA",) and d["id"] not in hidden]
    if len(idxs) < 2: continue
    recs = load(mp, meta)
    if not recs: continue
    for a in range(len(idxs)):
        for b in range(a+1, len(idxs)):
            ia, ib = idxs[a], idxs[b]
            pairs = set()
            av, bv = set(), set()
            for r in recs:
                pairs.add((r["k"][ia], r["k"][ib])); av.add(r["k"][ia]); bv.add(r["k"][ib])
            if not av or not bv: continue
            grid = len(av) * len(bv)
            fill = len(pairs) / grid
            fwd = defaultdict(set); rev = defaultdict(set)
            for x, y in pairs: fwd[x].add(y); rev[y].add(x)
            a_det = sum(1 for x in fwd if len(fwd[x]) == 1) / len(fwd)
            b_det = sum(1 for y in rev if len(rev[y]) == 1) / len(rev)
            if fill < 0.75 and max(a_det, b_det) > 0:
                findings.append({
                    "slug": meta["slug"], "flow": meta["name"],
                    "a": dims[ia]["name"], "b": dims[ib]["name"],
                    "a_n": len(av), "b_n": len(bv),
                    "fill": round(fill, 2), "a_det": round(a_det, 2), "b_det": round(b_det, 2),
                })

findings.sort(key=lambda f: (f["fill"], -max(f["a_det"], f["b_det"])))
(ROOT/"meta/dim_overlap.json").write_text(json.dumps(findings, indent=1))
print(f"dial pairs that are not independent: {len(findings)}\n")
print(f"{'fill':>5} {'A->B':>5} {'B->A':>5}  {'dial A':22} {'dial B':22} dataset")
for f in findings[:34]:
    print(f'{f["fill"]:5.2f} {f["a_det"]:5.2f} {f["b_det"]:5.2f}  '
          f'{f["a"][:22]:22} {f["b"][:22]:22} {f["flow"][:34]}')
