#!/usr/bin/env python3
"""Add population-normalised units using OECD's own historical population data
(DSD_POPULATION@DF_POP_HIST), cached in meta/aux/population.json.

Age bands are matched exactly where OECD publishes them and summed from
component bands otherwise, so the denominator always covers the same people as
the numerator.
"""
import json, gzip, pathlib, sys
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
POP = json.loads((ROOT/"meta/aux/population.json").read_text())

# how to build each age band from the bands OECD publishes
AGE_BUILD = {
    "Y15T24": [("+", "Y15T24")],
    "Y15T64": [("+", "Y15T64")],
    "Y20T64": [("+", "Y20T64")],
    "Y15T74": [("+", "Y15T64"), ("+", "Y65T69"), ("+", "Y70T74")],
    "Y25T54": [("+", "Y25T29"), ("+", "Y30T34"), ("+", "Y35T39"),
               ("+", "Y40T44"), ("+", "Y45T49"), ("+", "Y50T54")],
    "Y55T64": [("+", "Y55T59"), ("+", "Y60T64")],
    "Y_GE15": [("+", "_T"), ("-", "Y_LT15")],
    "Y_GE65": [("+", "Y_GE65")],
    "_T":     [("+", "_T")],
}

def pop_for(area, sex, age, year):
    recipe = AGE_BUILD.get(age)
    if not recipe: return None
    total = 0.0
    for sign, band in recipe:
        series = POP.get(f"{area}|{sex}|{band}")
        if not series: return None
        v = series.get(year)
        if v is None: return None
        total += v if sign == "+" else -v
    return total if total > 0 else None

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

def save(mp, meta, recs):
    d = mp.parent
    if meta["layout"] == "single":
        (d/"all.json.gz").write_bytes(gzip.compress(
            json.dumps(recs, separators=(",", ":")).encode(), 6))
    else:
        ai = next(i for i, x in enumerate(meta["dims"]) if x["id"] == meta["area_dim"])
        codes = meta["dims"][ai]["ids"]
        by = defaultdict(list)
        for r in recs: by[codes[r["k"][ai]]].append(r)
        parts = {}
        for code, rs in by.items():
            fn = (meta.get("parts") or {}).get(code, {}).get("file") or (
                "".join(c if c.isalnum() or c in "._-" else "_" for c in code) + ".json.gz")
            blob = gzip.compress(json.dumps(rs, separators=(",", ":")).encode(), 6)
            (d/"parts"/fn).write_bytes(blob)
            parts[code] = {"file": fn, "n": len(rs), "bytes": len(blob)}
        meta["parts"] = parts
    mp.write_text(json.dumps(meta, separators=(",", ":")))

def run(slug, new_code="PT_POP_D",
        new_label="Percentage of population in the same age group (derived)"):
    mp = FLOWS/slug/"meta.json"
    meta = json.loads(mp.read_text())
    idx = {d["id"]: i for i, d in enumerate(meta["dims"])}
    for need in ("REF_AREA", "UNIT_MEASURE", "AGE", "SEX"):
        if need not in idx: return f"{slug}: no {need}"
    ui, ai, gi, si = idx["UNIT_MEASURE"], idx["REF_AREA"], idx["AGE"], idx["SEX"]
    if new_code in meta["dims"][ui]["ids"]: return f"{slug}: already derived"

    recs = load(mp, meta)
    if not recs: return f"{slug}: no records"
    unit = meta["dims"][ui]
    unit["ids"].append(new_code); unit["names"].append(new_label)
    new_ui = len(unit["ids"]) - 1

    areas, sexes, ages = meta["dims"][ai]["ids"], meta["dims"][si]["ids"], meta["dims"][gi]["ids"]
    periods = meta["periods"]
    made = missing = 0
    out = list(recs)
    for r in recs:
        area, sex, age = areas[r["k"][ai]], sexes[r["k"][si]], ages[r["k"][gi]]
        t2, v2 = [], []
        for ti, v in zip(r["t"], r["v"]):
            year = str(periods[ti])[:4]
            den = pop_for(area, sex, age, year)
            if not den: continue
            # counts are published in thousands; population is in persons
            t2.append(ti); v2.append(round(v * 1000 / den * 100, 4))
        if not t2: missing += 1; continue
        k = list(r["k"]); k[ui] = new_ui
        out.append({"k": k, "t": t2, "v": v2})
        made += 1
    if not made:
        unit["ids"].pop(); unit["names"].pop()
        return f"{slug}: no population match"
    meta["n_series"] = len(out); meta["n_obs"] = sum(len(x["v"]) for x in out)
    meta.setdefault("derived_units", {})[new_code] = {
        "label": new_label, "over": "AGE", "total_code": "OECD population (DF_POP_HIST)",
        "method": "count divided by OECD's published population for the same country, "
                  "sex and age band, times 100",
    }
    save(mp, meta, out)
    return f"{slug}: +{made} derived series, {missing} without a population match"

for slug in (sys.argv[1:] or ["OECD.SDD.TPS__DF_IALFS_OLF_WAP_Q"]):
    print(run(slug))
