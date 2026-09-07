#!/usr/bin/env python3
"""Recompute the gig-work aggregates from the Observatory's raw daily files.

The two CSVs the builder reads are annual aggregates of daily observations. That
aggregation is the step that can be wrong, so it is redone here from the raw
figshare release and compared against what the site serves.
"""
import csv, gzip, json, pathlib, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SRC = pathlib.Path("/private/tmp/claude-501/-Users-alexhoffman-Documents/"
                   "5b734f3a-e90a-44b8-ab72-abd591c4d0c9/scratchpad")

d = ROOT/"site/data/flows/OII_OLI__DF_ONLINE_GIG"
m = json.loads((d/"meta.json").read_text())
recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
ai, mi = ids.index("REF_AREA"), ids.index("MEASURE")
oi = next(i for i, x in enumerate(m["dims"]) if x["id"] in ("OCCUPATION", "OCC"))
site = {}
for r in recs:
    k = (D["REF_AREA"]["ids"][r["k"][ai]], D["MEASURE"]["ids"][r["k"][mi]],
         D[ids[oi]]["ids"][r["k"][oi]])
    for t, v in zip(r["t"], r["v"]): site[(k, P[t])] = v
areas = set(D["REF_AREA"]["ids"])
occ_names = dict(zip(D[ids[oi]]["ids"], D[ids[oi]]["names"]))
OCC_IN = {v: k for k, v in occ_names.items()}

# ---- supply: daily worker counts -> annual mean -> share of the world total
daily = collections.defaultdict(list)
name_to_iso = {}
for mf in sorted((ROOT/"site/data/flows").glob("*/meta.json")):
    mm = json.loads(mf.read_text())
    for dd in mm.get("dims", []):
        if dd.get("id") == "REF_AREA":
            for c, n in zip(dd["ids"], dd["names"]): name_to_iso.setdefault(n, c)
# The world total must be taken over every country in the source, not only the
# ones still on the site. Keying by the source's own country name keeps the
# denominator whole; the ISO code is only needed to look the site value up.
for r in csv.DictReader(open(SRC/"oli_workers_src.txt")):
    o = OCC_IN.get(r["occupation"])
    if not o: continue
    try: n = float(r["num_workers"])
    except ValueError: continue
    daily[(r["country"], o, r["timestamp"][:4])].append(n)
annual = {k: sum(v)/len(v) for k, v in daily.items()}
W = collections.defaultdict(float)
for (a, o, y), n in annual.items():
    W[(a, o, y)] += n; W[(a, "_T", y)] += n
tot = collections.defaultdict(float)
for (a, o, y), n in W.items(): tot[(o, y)] += n
n_s = x_s = 0; ex = []
for (a, o, y), n in W.items():
    iso = name_to_iso.get(a)
    if not iso or iso not in areas: continue
    T = tot[(o, y)]
    if T <= 0: continue
    exp = n/T*100
    got = site.get(((iso, "SUPPLY_SHARE", o), y))
    if got is None: continue
    n_s += 1
    if abs(got - exp) > 0.05:
        x_s += 1
        if len(ex) < 4: ex.append((iso, o, y, round(exp,3), got))
print(f"supply shares: recomputed {n_s:,}  disagreeing {x_s}")
for e in ex: print("   ", e)

# ---- demand: daily counts -> annual mean -> rebased so 2016 = 100
dd = collections.defaultdict(list)
for r in csv.DictReader(open(SRC/"oli_demand_src.txt")):
    o = OCC_IN.get(r["occupation"])
    if not o or r.get("status") != "new": continue
    try: v = float(r["count"])
    except ValueError: continue
    dd[(o, r["date"][:4])].append(v)
A = {k: sum(v)/len(v) for k, v in dd.items()}
T = collections.defaultdict(float)
for (o, y), v in A.items(): T[("_T", y)] += v
A.update(T)
base = {o: A.get((o, "2016")) for o, _ in [(c, 0) for c in occ_names]}
n_d = x_d = 0; ex2 = []
for (o, y), v in A.items():
    b = base.get(o)
    if not b: continue
    exp = v/b*100
    got = site.get((("WLD", "DEMAND_IX", o), y))
    if got is None: continue
    n_d += 1
    if abs(got - exp) > 0.5:
        x_d += 1
        if len(ex2) < 4: ex2.append((o, y, round(exp,3), got))
print(f"demand index: recomputed {n_d:,}  disagreeing {x_d}")
for e in ex2: print("   ", e)
