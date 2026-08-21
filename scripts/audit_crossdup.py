#!/usr/bin/env python3
"""Find series duplicated across datasets.

Every series is fingerprinted by its actual numbers — the exact sequence of
(period, value) pairs. Two series with the same fingerprint are the same
measurement, whatever the two tables call it. This finds content that exists in
more than one place, so it can be kept once, where it is named correctly.
"""
import json, gzip, pathlib, hashlib
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
MIN_POINTS = 8          # short series collide by chance

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

fp = defaultdict(set)      # fingerprint -> {slug}
count = defaultdict(lambda: defaultdict(int))
names = {}
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    names[meta["slug"]] = meta["name"]
    per = meta["periods"]
    for r in load(mp, meta):
        if len(r["v"]) < MIN_POINTS: continue
        h = hashlib.blake2b(
            ("|".join(f"{per[t]}:{v:.6g}" for t, v in zip(r["t"], r["v"]))).encode(),
            digest_size=12).hexdigest()
        fp[h].add(meta["slug"])
        count[h][meta["slug"]] += 1

pairs = defaultdict(int)
for h, slugs in fp.items():
    if len(slugs) < 2: continue
    s = sorted(slugs)
    for i in range(len(s)):
        for j in range(i+1, len(s)):
            pairs[(s[i], s[j])] += 1

tot = {}
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    tot[meta["slug"]] = sum(1 for r in load(mp, meta) if len(r["v"]) >= MIN_POINTS)

rows = []
for (a, b), n in pairs.items():
    rows.append({"a": a, "b": b, "shared": n,
                 "a_name": names[a], "b_name": names[b],
                 "a_share": round(n/max(tot[a], 1), 3),
                 "b_share": round(n/max(tot[b], 1), 3)})
rows.sort(key=lambda r: -max(r["a_share"], r["b_share"]))
(ROOT/"meta/cross_duplicates.json").write_text(json.dumps(rows, indent=1))

print(f"dataset pairs sharing identical series: {len(rows)}\n")
print(f"{'shared':>7} {'of A':>6} {'of B':>6}  dataset A / dataset B")
for r in rows[:26]:
    print(f'{r["shared"]:7} {r["a_share"]*100:5.0f}% {r["b_share"]*100:5.0f}%  '
          f'{r["a_name"][:38]:38} / {r["b_name"][:38]}')
