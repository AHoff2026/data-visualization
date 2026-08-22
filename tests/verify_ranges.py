#!/usr/bin/env python3
"""Flag values that cannot mean what their unit says.

A share of a population cannot exceed 100, and a count cannot be negative. Where
that happens the unit label and the number disagree, and one of them is wrong.
"""
import json, gzip, pathlib, re
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
# units where a value above 100 is impossible rather than merely unusual
BOUNDED = re.compile(r"percentage of (the )?(population|employment|labor force|"
                     r"labour force|employees|students|respondents|households|unemployed|"
                     r"working-age population)", re.I)
NONNEG = re.compile(r"^(persons?|number|thousands?|households?|hours per|percentage)", re.I)

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
    ui = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "UNIT_MEASURE"), None)
    ai = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "REF_AREA"), None)
    if ui is None: continue
    ti = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "TRANSFORMATION"), None)
    over = defaultdict(int); neg = defaultdict(int); worst = defaultdict(float)
    areas = defaultdict(set)
    for r in load(mp, meta):
        # a growth rate is legitimately negative and unbounded, whatever the
        # unit of the level it was computed from
        if ti is not None and re.search(r"growth|change",
                meta["dims"][ti]["names"][r["k"][ti]], re.I):
            continue
        un = meta["dims"][ui]["names"][r["k"][ui]]
        bounded = bool(BOUNDED.search(un)); nonneg = bool(NONNEG.match(un))
        for v in r["v"]:
            if bounded and v > 100.5:
                over[un] += 1; worst[un] = max(worst[un], v)
                if ai is not None: areas[un].add(meta["dims"][ai]["ids"][r["k"][ai]])
            if nonneg and v < 0: neg[un] += 1
    for un, n in over.items():
        rows.append(("above 100", meta["name"], un, n, round(worst[un], 1), sorted(areas[un])[:4]))
    for un, n in neg.items():
        rows.append(("negative", meta["name"], un, n, 0, []))

rows.sort(key=lambda r: -r[3])
print(f"unit/value contradictions: {len(rows)}\n")
for kind, flow, un, n, w, ar in rows[:22]:
    print(f'  {kind:9} {n:7} values (max {w:>10})  {un[:38]:38} {flow[:30]}  {ar}')
