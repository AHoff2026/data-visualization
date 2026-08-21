#!/usr/bin/env python3
"""Survey every dataset: which MEASURE x UNIT_MEASURE combinations actually
carry data, how well covered they are, and whether the unit is a comparable
rate or an absolute count that needs normalising."""
import json, gzip, pathlib, re
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
CAT = json.loads((ROOT/"site/data/catalog.json").read_text())
CORE = set(CAT["core_areas"])

RATE = re.compile(r'percent|per cent|%|ratio|rate|index|per capita|per head|per person|'
                  r'per 1|per thousand|per 100|share', re.I)
COUNT = re.compile(r'^(persons?|number|thousands?|millions?|units?|head)', re.I)
MONEY = re.compile(r'dollar|euro|currency|national currency|xdc|ppp', re.I)

def load(mp, meta):
    d = mp.parent
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for info in (meta.get("parts") or {}).values():
        f = d/"parts"/info["file"]
        if f.exists(): out.extend(json.loads(gzip.decompress(f.read_bytes())))
    return out

rows = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    dims = meta["dims"]
    idx = {d["id"]: i for i, d in enumerate(dims)}
    ui, mi, ai = idx.get("UNIT_MEASURE"), idx.get("MEASURE"), idx.get("REF_AREA")
    recs = load(mp, meta)
    if not recs: continue
    agg = defaultdict(lambda: {"obs":0,"areas":set(),"core":set(),"t0":10**9,"t1":-1})
    for r in recs:
        u = dims[ui]["ids"][r["k"][ui]] if ui is not None else "_"
        m = dims[mi]["ids"][r["k"][mi]] if mi is not None else "_"
        a = dims[ai]["ids"][r["k"][ai]] if ai is not None else "_"
        g = agg[(m,u)]
        g["obs"] += len(r["v"]); g["areas"].add(a)
        if a in CORE: g["core"].add(a)
        if r["t"]: g["t0"]=min(g["t0"],r["t"][0]); g["t1"]=max(g["t1"],r["t"][-1])
    for (m,u), g in agg.items():
        uname = dims[ui]["names"][dims[ui]["ids"].index(u)] if ui is not None else ""
        mname = dims[mi]["names"][dims[mi]["ids"].index(m)] if mi is not None else ""
        kind = ("rate" if RATE.search(uname) else
                "money" if MONEY.search(uname) else
                "count" if COUNT.search(uname) else "other")
        rows.append({
            "slug": meta["slug"], "flow": meta["name"],
            "measure": m, "measure_name": mname,
            "unit": u, "unit_name": uname, "kind": kind,
            "obs": g["obs"], "areas": len(g["areas"]), "core_areas": len(g["core"]),
            "from": meta["periods"][g["t0"]] if g["t1"]>=0 else None,
            "to": meta["periods"][g["t1"]] if g["t1"]>=0 else None,
        })

(ROOT/"meta/audit.json").write_text(json.dumps(rows, indent=1))

from collections import Counter
print(f"measure x unit combinations with data: {len(rows)}")
print("by kind:", dict(Counter(r["kind"] for r in rows)))
print()
# flows whose every unit is an absolute count -> nothing comparable to chart
byflow = defaultdict(list)
for r in rows: byflow[r["slug"]].append(r)
countonly = [(s, v[0]["flow"]) for s, v in byflow.items()
             if v and all(x["kind"] in ("count",) for x in v)]
print(f"DATASETS WITH NO COMPARABLE RATE ({len(countonly)}) — counts only:")
for s, n in countonly: print(f"   {n[:70]}")
print()
thin = [r for r in rows if r["core_areas"] <= 3]
print(f"COMBINATIONS COVERING <=3 CORE COUNTRIES: {len(thin)} of {len(rows)}")
for r in sorted(thin, key=lambda x: x["core_areas"])[:12]:
    print(f'   {r["core_areas"]:2} core · {r["obs"]:7} obs · {r["flow"][:40]:40} · {r["unit_name"][:34]}')
