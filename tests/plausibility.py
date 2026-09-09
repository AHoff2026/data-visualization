import re
#!/usr/bin/env python3
"""Does every series pass a smell test?

Not sampling: every series, against rules that encode what social and labour
statistics cannot do. A share cannot exceed 100. A subgroup cannot exceed the
total it sits inside. A decile ratio cannot be below one. An ordinal scale cannot
leave its own range. A rate does not move sixty points in a year.

Rules are deliberately conservative: a flag is a question, not a verdict.
"""
import json, gzip, pathlib, collections, math, sys

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"
TOTAL_CODES = {"_T", "T", "TOTAL", "_Z"}
# Whether a dimension's categories partition its total is decided from the data,
# not from a list of unit codes. Hand curation kept missing siblings: PT_EMP was
# listed as a rate while PT_EMP_PT, the same measure over a different base, was
# not, so the same dataset was flagged through the unit nobody had got to yet.
#
# The test: bucket every cell by (other dimensions, unit, period) and compare the
# sum of the categories against the total. Sum near the total means the categories
# partition it, so each is a share of it, bounded 0-100, and none may exceed it.
# Anything else is a rate within a subgroup whose total is a weighted average --
# the male employment rate is above the overall rate in every country on earth --
# and neither rule means anything there.
PARTITION_TOL = 0.05      # a category sum within 5% of the total counts as summing
PARTITION_SHARE = 0.8     # and 80% of cells must do so before the rule applies
PARTITION_MIN = 20        # on at least this many cells, else there is nothing to go on
# Regional rows are averaged over whichever members reported each cell, so a
# component may exceed its total there without anything being wrong. The site
# says so on every dataset that offers one (scripts/note_aggregates.py), and all
# 522 violations in social expenditure were the OECD row alone, no country.
AGG_AREA = re.compile(r"^(OECD|OECD_REP|EU\d*|EU\d+_\d+|EU\d+OECD|EUOECD|EA\d*|G7|G20|WLD)$")
# Relative-to-reference units: the reference group is 100 and a value above it means
# "earns more than the reference", which is the whole point of the measure. Not a
# bounded share, and its "Total" is a reference point rather than a ceiling.
REFERENCE_UNITS = ("PT_EARN_WR", "IX", "PT_EARN_REL")
# Indicators that are legitimately below one; the ratio rule must not flag them.
SUB_ONE_OK = {"PAL_INC_DISP", "PALMA", "ATKINSON", "GINI_PRETAX", "GINI_DHI",
              "GINI_WB", "GINI_LONGRUN"}
# Scores of law rather than measurements: they are meant to sit still for years.
STATIC_OK = {"OECD.ELS.JAI__DF_EPL", "OECD.ELS.JAI__DF_SBE", "OECD_AIAS__ICTWSS",
             "OECD.ELS.SPD__DF_DPS"}
# units whose values are bounded shares
PCT = lambda u: ((u.startswith("PT") or u in {"PC", "PT_POP", "PT_B1GQ"})
                 and not u.startswith(REFERENCE_UNITS))


def partition_map(recs, meta, ids, D, ui):
    """Which (dimension, unit) pairs have categories that sum to their total.

    Returns a dict keyed by (dimension index, unit code) -> True/False, plus the
    set of units that partition somewhere, which is what makes a value provably a
    share of a whole and so bounded 0-100.
    """
    out, bounded = {}, set()
    for i, d in enumerate(meta["dims"]):
        if d["id"] in ("REF_AREA", "UNIT_MEASURE", "TIME_PERIOD"): continue
        tot = next((c for c in d["ids"] if c in TOTAL_CODES), None)
        if tot is None or len(d["ids"]) < 3: continue
        ti = d["ids"].index(tot)
        buckets = collections.defaultdict(dict)
        for r in recs:
            u = D["UNIT_MEASURE"]["ids"][r["k"][ui]] if ui is not None else ""
            key = (tuple(v for j, v in enumerate(r["k"]) if j != i), u)
            for t, v in zip(r["t"], r["v"]): buckets[(key, t)][r["k"][i]] = v
        by_unit = collections.defaultdict(list)
        for ((key, u), t), mm in buckets.items():
            if ti not in mm or len(mm) < 3: continue
            T = mm[ti]
            if T <= 0: continue
            by_unit[u].append(sum(v for j, v in mm.items() if j != ti)/T)
        for u, ratios in by_unit.items():
            if len(ratios) < PARTITION_MIN:
                out[(i, u)] = False
                continue
            near = sum(1 for x in ratios
                       if 1-PARTITION_TOL <= x <= 1+PARTITION_TOL)/len(ratios)
            ok = near > PARTITION_SHARE
            out[(i, u)] = ok
            if ok: bounded.add(u)
    return out, bounded

def load(d, m):
    if m["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for f in sorted((d/"parts").glob("*.json.gz")):
        out += json.loads(gzip.decompress(f.read_bytes()))
    return out

findings = []
def flag(rule, slug, name, detail, severity="check"):
    findings.append({"rule": rule, "slug": slug, "dataset": name,
                     "detail": detail, "severity": severity})

for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text()); recs = load(mp.parent, meta)
    if not recs: continue
    slug, nm = meta["slug"], meta["name"]
    ids = [x["id"] for x in meta["dims"]]
    D = {x["id"]: x for x in meta["dims"]}
    P = meta["periods"]
    ui = ids.index("UNIT_MEASURE") if "UNIT_MEASURE" in ids else None
    mi = next((i for i, x in enumerate(meta["dims"])
               if x["id"] in ("MEASURE", "ITEM", "INDICATOR")), None)

    partitions, bounded_units = partition_map(recs, meta, ids, D, ui)

    # ---- R1 share out of range, R6 impossible year-on-year move, R5 frozen series
    n_out = n_jump = n_flat = 0
    ex_out = ex_jump = None
    for r in recs:
        unit = D["UNIT_MEASURE"]["ids"][r["k"][ui]] if ui is not None else ""
        vals = r["v"]
        # Out of range is only impossible for a unit that is demonstrably a share
        # of a whole. A replacement rate above 100, a negative wage gap and a
        # participation tax over 100% are all the measure working as intended.
        if PCT(unit) and unit in bounded_units:
            for t, v in zip(r["t"], vals):
                if v < -0.001 or v > 100.001:
                    n_out += 1
                    if ex_out is None: ex_out = (P[t], v)
        # A jump of sixty points in a year is worth a look on any percentage,
        # bounded or not, so this is deliberately outside the check above.
        if PCT(unit):
            for (t0, v0), (t1, v1) in zip(zip(r["t"], vals), list(zip(r["t"], vals))[1:]):
                try: gap = int(P[t1][:4]) - int(P[t0][:4])
                except ValueError: gap = 1
                if gap == 1 and abs(v1 - v0) > 60:
                    n_jump += 1
                    if ex_jump is None: ex_jump = (P[t0], v0, P[t1], v1)
        if len(vals) >= 12 and len(set(vals)) == 1 and vals[0] != 0:
            n_flat += 1
    if n_out: flag("share outside 0-100", slug, nm,
                   f"{n_out} values, e.g. {ex_out[0]}: {ex_out[1]:.2f}", "high")
    if n_jump: flag("moves >60 points in one year", slug, nm,
                    f"{n_jump} steps, e.g. {ex_jump[0]}:{ex_jump[1]:.1f} -> {ex_jump[2]}:{ex_jump[3]:.1f}")
    if n_flat and slug not in STATIC_OK:
        flag("identical value for 12+ periods", slug, nm, f"{n_flat} series")

    # ---- R2 a breakdown category exceeding its own total
    for i, d in enumerate(meta["dims"]):
        if d["id"] in ("REF_AREA", "UNIT_MEASURE", "MEASURE", "TIME_PERIOD"): continue
        tot = next((c for c in d["ids"] if c in TOTAL_CODES), None)
        if tot is None or len(d["ids"]) < 3: continue
        ti = d["ids"].index(tot)
        buckets = collections.defaultdict(dict)
        ai = ids.index("REF_AREA") if "REF_AREA" in ids else None
        for r in recs:
            unit = D["UNIT_MEASURE"]["ids"][r["k"][ui]] if ui is not None else ""
            if not PCT(unit): continue
            if not partitions.get((i, unit)): continue
            if ai is not None and AGG_AREA.match(D["REF_AREA"]["ids"][r["k"][ai]]):
                continue
            key = tuple(v for j, v in enumerate(r["k"]) if j != i)
            for t, v in zip(r["t"], r["v"]): buckets[(key, t)][r["k"][i]] = v
        bad = 0; ex = None
        for (key, t), mm in buckets.items():
            if ti not in mm: continue
            T = mm[ti]
            if T <= 0: continue
            for j, v in mm.items():
                if j != ti and v > T * 1.02 + 0.5:
                    bad += 1
                    if ex is None: ex = (d["names"][j], v, d["names"][ti], T, P[t])
        if bad:
            flag("category exceeds its own total", slug, nm,
                 f'{d["name"]}: {bad} cases, e.g. "{ex[0]}" {ex[1]:.1f} > "{ex[2]}" {ex[3]:.1f} in {ex[4]}',
                 "high")

    # ---- R7 a ratio below one
    if ui is not None:
        for r in recs:
            unit = D["UNIT_MEASURE"]["ids"][r["k"][ui]]
            if unit not in ("RATIO", "FCTR"): continue
            mcode = D[ids[mi]]["ids"][r["k"][mi]] if mi is not None else ""
            if mcode in SUB_ONE_OK: continue
            bad = [v for v in r["v"] if v < 1]
            if bad:
                flag("ratio below 1", slug, nm,
                     f'{mcode}: {len(bad)} values, min {min(bad):.3f}', "high")

print(f"{len(findings)} flags\n")
by = collections.Counter(f["rule"] for f in findings)
for k, v in by.most_common(): print(f"  {v:>4}  {k}")
print()
for f in sorted(findings, key=lambda f: (f["severity"] != "high", f["dataset"])):
    mark = "!!" if f["severity"] == "high" else "  "
    print(f'{mark} {f["dataset"][:38]:40} {f["rule"][:32]:34} {f["detail"][:92]}')
json.dump(findings, open("/tmp/plausibility.json", "w"), indent=1)

# ---- a default view that cannot say anything -----------------------------
# A reference group plotted against itself is constant at 100 by construction.
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    b = (meta.get("default_bundle") or {}).get("picks") or {}
    unit = b.get("UNIT_MEASURE", "")
    for k, v in b.items():
        if k != "UNIT_MEASURE" and v and unit.endswith(v):
            print(f'!! {meta["name"][:38]:40} default view is self-referential: '
                  f'{k}={v} against unit {unit}')
