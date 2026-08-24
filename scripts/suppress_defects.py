#!/usr/bin/env python3
"""Suppress observations that the source publishes but that cannot be true.

Every entry here was traced to the primary source and confirmed to be present
there, flagged "normal value". Reproducing them faithfully is not a virtue when
the result is a chart that reads as a collapse to zero or a thousandfold jump.
They are removed as the missing values they are, and each rule states what the
evidence was.

This is deliberately a hand-written list, not a rule. A blanket "drop outliers"
pass would remove real history -- benefit cliffs, hyperinflation, the pandemic.
"""
import json, gzip, pathlib

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"

# slug -> list of rules. A rule matches an observation when every code named in
# "where" matches and, if given, the period is in "years".
RULES = {
  "OECD.SDD.TPS__DF_ALFS_EMP": [
    {"where": {"REF_AREA": "TUR", "WORKER_STATUS": "ICSE93_1"},
     "min_year": 2021,
     "why": "Turkey's employee count breaks scale by three orders of magnitude from "
            "2021: 12,989 thousand in 2020 against 10.8 in 2021, while total employment "
            "is unchanged. The derived share falls from 70 per cent to 0.06 per cent."},
    {"where": {"REF_AREA": "LTU", "WORKER_STATUS": "ICSE93_5", "SEX": "_T"},
     "years": {"2005","2006","2007","2008","2010","2011","2012","2014","2015"},
     "why": "The total for contributing family workers is a copy of the male series in "
            "these years, so it sits below the female figure it is supposed to contain."},
  ],
  "OECD.ELS.SPD__DF_SOCX_AGG": [
    {"where": {"REF_AREA": "CRI", "PROGRAMME_TYPE": "TP41", "SPENDING_TYPE": "_T"},
     "max_year": 2010,
     "why": "Costa Rican health spending totals read about one eighty-fifth of their "
            "in-kind component, which has no cash counterpart. Health spending is near "
            "6 per cent of GDP; the total series reads 0.05."},
    {"where": {"REF_AREA": "GBR", "UNIT_MEASURE": "PT_OTE_S13"}, "years": {"1989"},
     "why": "Social spending reads 164 per cent of all government expenditure in the "
            "first year after a gap, against 44 per cent the following year."},
    {"where": {"REF_AREA": "JPN", "UNIT_MEASURE": "PT_OTE_S13"}, "years": {"2004"},
     "why": "Social spending reads 188 per cent of all government expenditure in the "
            "first year after a gap, against 48 per cent the following year."},
  ],
  "OECD.WISE.INE__DF_IDD": [
    {"where": {"REF_AREA": "CAN", "MEASURE": "D9_1_INC_DISP"}, "years": {"2010"},
     "why": "Decile ratio published as zero between 4.5 and 4.4 in the neighbouring "
            "years. A P90/P10 ratio cannot be zero."},
    {"where": {"REF_AREA": "CAN", "MEASURE": "D9_5_INC_DISP"}, "years": {"2010"},
     "why": "Decile ratio published as zero between 1.9 and 1.9 in the neighbouring "
            "years."},
  ],
  "OECD_AIAS__ICTWSS": [
    {"where": {"REF_AREA": "LUX", "MEASURE": "UD_age5564_s"}, "years": {"2018"},
     "why": "Union density of 354.7 per cent, on a series otherwise running 32 to 42."},
    {"where": {"REF_AREA": "LUX", "MEASURE": "UD_age5064_s"}, "years": {"2019"},
     "why": "Union density of 342.6 per cent, on a series otherwise running 35 to 42."},
    {"where": {"REF_AREA": "EST", "MEASURE": "UD_female_s"}, "years": {"2021"},
     "why": "Women's union density of 60.0 between 6.4 and 7.0 in the adjacent years."},
  ],
}
# Values that are impossible for their own unit, applied across a whole dataset.
BOUNDS = {
  "OECD.ELS.SAE__DF_TENURE_AVE": {"unit_any": True, "min": 0.0, "max": 60.0,
     "why": "Average job tenure below zero or above sixty years is not a measurement."},
  "OECD.ELS.SAE__DF_INVPT_I": {"pct": True, "min": 0.0, "max": 100.0,
     "why": "A share of part-time employment above 100 per cent is not a measurement."},
}

def load(d, m):
    if m["layout"] == "single":
        f = d/"all.json.gz"
        return {"all.json.gz": json.loads(gzip.decompress(f.read_bytes()))} if f.exists() else {}
    return {f.name: json.loads(gzip.decompress(f.read_bytes()))
            for f in sorted((d/"parts").glob("*.json.gz"))}

def save(d, m, chunks):
    if m["layout"] == "single":
        (d/"all.json.gz").write_bytes(gzip.compress(
            json.dumps(chunks["all.json.gz"], separators=(",", ":")).encode(), 6))
    else:
        for fn, recs in chunks.items():
            p = d/"parts"/fn
            p.write_bytes(gzip.compress(json.dumps(recs, separators=(",", ":")).encode(), 6))
            for code, info in m.get("parts", {}).items():
                if isinstance(info, dict) and info.get("file") == fn:
                    info["n"] = sum(len(r["v"]) for r in recs)
                    info["bytes"] = p.stat().st_size

total = 0
for slug in sorted(set(RULES) | set(BOUNDS)):
    d = FLOWS/slug
    if not (d/"meta.json").exists(): continue
    meta = json.loads((d/"meta.json").read_text())
    ids = [x["id"] for x in meta["dims"]]
    D = {x["id"]: x for x in meta["dims"]}
    P = meta["periods"]
    ui = ids.index("UNIT_MEASURE") if "UNIT_MEASURE" in ids else None
    chunks = load(d, meta)
    removed = 0

    for fn, recs in chunks.items():
        out = []
        for r in recs:
            codes = {ids[i]: D[ids[i]]["ids"][v] for i, v in enumerate(r["k"])}
            unit = codes.get("UNIT_MEASURE", "")
            drop_all = []
            for rule in RULES.get(slug, []):
                if all(codes.get(k) == v for k, v in rule["where"].items()):
                    drop_all.append(rule)
            b = BOUNDS.get(slug)
            keep_t, keep_v, keep_s = [], [], []
            src = r.get("s")
            for j, (t, v) in enumerate(zip(r["t"], r["v"])):
                y = P[t][:4]
                gone = False
                for rule in drop_all:
                    if "years" in rule and y not in rule["years"]: continue
                    if "min_year" in rule and int(y) < rule["min_year"]: continue
                    if "max_year" in rule and int(y) > rule["max_year"]: continue
                    gone = True; break
                if not gone and b:
                    applies = b.get("unit_any") or (b.get("pct") and unit.startswith("PT"))
                    if applies and (v < b["min"] or v > b["max"]): gone = True
                if gone: removed += 1; continue
                keep_t.append(t); keep_v.append(v)
                if src is not None: keep_s.append(src[j])
            if keep_v:
                n = dict(r); n["t"] = keep_t; n["v"] = keep_v
                if src is not None: n["s"] = keep_s
                out.append(n)
        chunks[fn] = out

    if removed:
        allrecs = [r for recs in chunks.values() for r in recs]
        meta["n_series"] = len(allrecs)
        meta["n_obs"] = sum(len(r["v"]) for r in allrecs)
        save(d, meta, chunks)
        (d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
        print(f'  {meta["name"][:44]:46} {removed:>6,} observations suppressed')
        total += removed
print(f"\n{total:,} observations suppressed as upstream defects.")
