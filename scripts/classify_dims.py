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
    "QUESTIONNAIRE":        [],                     # collection round: no analytical content
    "CONVERSION_TYPE":      ["PPP", "_Z"],          # PPP where offered
    "TIME_HORIZ":           ["H", "_T"],
    "JOB_COVERAGE":         ["MAIN", "_T"],
    "FREQ":                 ["A"],                  # annual: these are trend charts
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
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    hidden = {}
    for d in meta["dims"]:
        if d["id"] in RENAME and d["name"] != RENAME[d["id"]]:
            d["name"] = RENAME[d["id"]]; renamed += 1
        if len(d["ids"]) <= 1: continue
        if d["id"] not in TECHNICAL: continue
        pick = None
        for c in TECHNICAL[d["id"]]:
            if c in d["ids"]: pick = c; break
        if pick is None: pick = d["ids"][0]
        hidden[d["id"]] = pick
        hidden_total += 1
    meta["hidden_dims"] = hidden
    mp.write_text(json.dumps(meta, separators=(",", ":")))

print(f"technical dials folded away: {hidden_total}")
print(f"dimension labels clarified : {renamed}")
