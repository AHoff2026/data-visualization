#!/usr/bin/env python3
"""Find measure/unit combinations inside one dataset that are the same numbers.

The part-time case: a table shipped an extra measure whose series were identical
to a differently-named one. Same numbers under two names is worse than
redundant, because the two names imply two different questions.
"""
import json, gzip, pathlib, hashlib
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
MIN = 6

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
    idx = {d["id"]: i for i, d in enumerate(meta["dims"])}
    mi, ui = idx.get("MEASURE"), idx.get("UNIT_MEASURE")
    if mi is None and ui is None: continue
    per = meta["periods"]
    # fingerprint every series, grouped by its (measure, unit) combination
    combo = defaultdict(set); counts = defaultdict(int)
    for r in load(mp, meta):
        if len(r["v"]) < MIN: continue
        h = hashlib.blake2b(
            ("|".join(f"{per[t]}:{v:.6g}" for t, v in zip(r["t"], r["v"]))).encode(),
            digest_size=10).hexdigest()
        key = (r["k"][mi] if mi is not None else 0, r["k"][ui] if ui is not None else 0)
        combo[key].add(h); counts[key] += 1
    keys = [k for k in combo if counts[k] >= 8]
    for a in range(len(keys)):
        for b in range(a+1, len(keys)):
            ka, kb = keys[a], keys[b]
            inter = combo[ka] & combo[kb]
            if not inter: continue
            share = len(inter) / min(len(combo[ka]), len(combo[kb]))
            if share < 0.9: continue
            def nm(k):
                m_ = meta["dims"][mi]["names"][k[0]] if mi is not None else ""
                u_ = meta["dims"][ui]["names"][k[1]] if ui is not None else ""
                return f"{m_} / {u_}".strip(" /")
            rows.append((meta["name"], nm(ka), nm(kb), len(inter),
                         counts[ka], counts[kb], round(share, 2)))

rows.sort(key=lambda r: -r[3])
print(f"identical measure/unit pairs inside a dataset: {len(rows)}\n")
for n, a, b, shared, ca, cb, sh in rows[:20]:
    print(f"  {shared:6} identical ({sh*100:3.0f}%)  {a[:34]:34} = {b[:34]:34}  {n[:28]}")
