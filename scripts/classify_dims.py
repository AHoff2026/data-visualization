#!/usr/bin/env python3
"""Decide which dials earn a place in the interface.

A dial earns its place if changing it answers a question a reader would
actually ask. Technical dials — seasonal adjustment, index vs level, which
questionnaire collected it — change the number without changing the question,
so they are set to a sensible value and folded away under "Advanced" rather
than sitting in the main row competing for attention.
"""
import json, pathlib

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

# dimension -> codes to prefer, best first
TECHNICAL = {
    "TRANSFORMATION":       ["_Z", "N"],            # levels, not index or growth
    "ADJUSTMENT":           ["Y", "N"],             # seasonally adjusted where offered
    "STATISTICAL_OPERATION":["OBS", "_Z"],          # the estimate, not its standard error
    "METHODOLOGY":          ["OECD_DEF", "_T"],     # the harmonized definition
    "QUESTIONNAIRE":        ["NEAC", "EARN", "TRANS"],  # the regular collection covers every member
    "CONVERSION_TYPE":      ["PPP", "_Z"],          # PPP where offered
    "TIME_HORIZ":           ["H", "_T"],
    "JOB_COVERAGE":         ["MAIN", "_T"],
    "FREQ":                 ["A"],                  # annual: these are trend charts
    # tax-benefit scenarios: these switch the assumptions behind the simulation
    # rather than the question being asked, so they sit under Advanced at the
    # case OECD itself treats as standard.
    "AGE_CHILDREN":         ["Y4_6", "Y2_3"],
    "CHILDCARE_USE":        ["NO", "YES"],
    "HOUSE_BENEFIT":        ["NO", "YES"],
    "TEMP_INTOWORK_BENEFIT": ["NO", "YES"],
    "SOC_ASS_BENEFIT":      ["YES", "NO", "_Z"],     # the realistic case: top-ups claimed
    "INCOME_PART":          ["_Z", "NOEARN_UNEMP_WO_CONBEN"],   # single-earner case
    "TABLE_IDENTIFIER":     [],
    "DECIMALS":             [],
    "UNIT_MULT":            [],
    "OBS_STATUS":           [],
}
# clearer names for the dials that stay
RENAME = {
    "UNIT_MEASURE": "Measured as",
    "MEASURE": "Indicator",
    "REF_AREA": "Country",
    "WORK_TIME_ARNGMNT": "Working time",
    "ATTAINMENT_LEV": "Education level",
    "BIRTH_PLACE": "Place of birth",
    "EXPEND_SOURCE": "Funded by",
    "PROGRAMME_TYPE": "Program",
    "SPENDING_TYPE": "Spending type",
    "WORKER_STATUS": "Worker status",
    "LABOUR_FORCE_STATUS": "Labor force status",
    "AGGREGATION_OPERATION": "Statistic",
    "STANDARD_REVENUE": "Revenue type",
    "INST_TYPE_EDU": "Institution type",
    "EDU_STATUS": "Education status",
    "MIGRATION_AGE": "Age at migration",
    "EMP_STATUS": "Employment status",
    "GEO_AREA": "Area type",
    "INCOME_PRINCIPAL": "Principal earner income",
    "INCOME_SPOUSE": "Spouse income",
    "INCOME_CURR": "Wage level",
    "HOUSE_BENEFIT": "Housing benefit",
    "TEMP_INTOWORK_BENEFIT": "In-work benefit",
    "EDUCATION_FIELD": "Field of study",
    "EDUCATION_LEV": "Education program",
    "EDUCATION_LEVEL": "Education level",
    "ASSET_CODE": "Asset",
    "INSTR_ASSET": "Asset or instrument",
    "PRICE_BASE": "Prices",
}

hidden_total = renamed = 0
def observation_counts(mp, meta):
    import gzip
    d = mp.parent
    recs = []
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        if f.exists(): recs = json.loads(gzip.decompress(f.read_bytes()))
    else:
        for info in (meta.get("parts") or {}).values():
            f = d/"parts"/info["file"]
            if f.exists(): recs += json.loads(gzip.decompress(f.read_bytes()))
    out = {}
    for i, dim in enumerate(meta["dims"]):
        if dim["id"] not in TECHNICAL or len(dim["ids"]) <= 1: continue
        c = {}
        for r in recs: c[dim["ids"][r["k"][i]]] = c.get(dim["ids"][r["k"][i]], 0) + len(r["v"])
        out[dim["id"]] = c
    return out

for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    obs_by_code = observation_counts(mp, meta)
    hidden = {}
    for d in meta["dims"]:
        if d["id"] in RENAME and d["name"] != RENAME[d["id"]]:
            d["name"] = RENAME[d["id"]]; renamed += 1
        if len(d["ids"]) <= 1: continue
        if d["id"] not in TECHNICAL: continue
        pick = None
        for c in TECHNICAL[d["id"]]:
            if c in d["ids"]: pick = c; break
        if pick is None:
            # no stated preference: take whichever value carries the most data,
            # rather than whichever happens to sort first
            counts = obs_by_code.get(d["id"], {})
            pick = max(d["ids"], key=lambda c: counts.get(c, 0)) if counts else d["ids"][0]
        hidden[d["id"]] = pick
        hidden_total += 1
    meta["hidden_dims"] = hidden
    mp.write_text(json.dumps(meta, separators=(",", ":")))

print(f"technical dials folded away: {hidden_total}")
print(f"dimension labels clarified : {renamed}")
