#!/usr/bin/env python3
"""Editorial label decisions, applied after the generic label steps.

These are judgements made against the data, not mechanical transforms, so they
live here rather than in anyone's memory: re-running the pipeline must not undo
them.
"""
import json, pathlib, re

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

# OECD writes "percentage of X in the same subgroup". The qualifier matters —
# the denominator is the group the breakdowns define — but "subgroup" is jargon.
GENERIC = {
    "PT_POP_SUB": "Percentage of the same population group",
    "PT_LF_SUB":  "Percentage of the same labor force group",
    "PT_WAP_SUB": "Percentage of the same working-age group",
    "PT_ST_SUB":  "Percentage of the same student group",
    "PT_EMP_SUB": "Percentage of the same employed group",
}
# where the group is knowable and was checked against the values
CONCRETE = {
    "OECD.ELS.SAE__DF_TEMP_I_GEN":   {"UNIT_MEASURE": {"PT_POP_SUB": "Percentage of temporary employees"}},
    "OECD.ELS.SAE__DF_FTPT_INC_GEN": {"UNIT_MEASURE": {"PT_POP_SUB": "Percentage of part-time workers"}},
    # two different denominators OECD gives the same words to
    "OECD.CTP.TPS__DF_RSGLOBAL":     {"UNIT_MEASURE": {
        "PT_OTR_REV_CAT": "Percentage of revenues in the same tax category",
        "PT_OTR_SECTOR":  "Percentage of revenues of the same level of government"}},
    # two distinct activity totals that a generic rename collapsed into one
    "OECD.SDD.TPS__DF_ALFS_EMP":     {"ACTIVITY": {"ATU": "All activities (ISIC)",
                                                   "_T": "All activities"}},
    # "Central" is a continuous summary index, not one of the coded ordinal
    # scales, so it carries no value key and the generic "ordinal code" label
    # misdescribed it.
    "OECD_AIAS__ICTWSS":             {"UNIT_MEASURE": {
        "SCALE": "Ordinal code, see the key below the chart"}},
    # These categories nest: "Public" is contained in "Public plus mandatory
    # private". Read side by side under OECD's own wording the smaller figure looks
    # like an error, so the labels say which contain which.
    "OECD.ELS.SPD__DF_SOCX_AGG":     {"EXPEND_SOURCE": {
        "ES10":    "Public only",
        "ES20":    "Mandatory private only",
        "ES30":    "Voluntary private only",
        "ES10_20": "Public plus mandatory private",
        "ES20_30": "Mandatory plus voluntary private",
        "ES40":    "Public, net of tax paid back",
        "ES50":    "Total, net of tax (public and private)"}},
    # verified against Germany's published rates: these are levels, not growth
    "OECD.SDD.TPS__DF_SUMTAB":       {"TRANSFORMATION": {"G1": "Level"},
        # Published as "Employment rate" but carrying only male and female, which
        # sum to 100 in 2,078 of 2,099 country-years. It is the sex split of
        # employment, not a rate against the working-age population.
        "MEASURE": {"EMP_WAP": "Share of employment, by sex"}},
}
SUFFIX = re.compile(r"\s+in the same\b[^,;]*$", re.I)

n = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text()); changed = False
    over = CONCRETE.get(meta["slug"], {})
    for d in meta["dims"]:
        table = over.get(d["id"], {})
        for j, cid in enumerate(d["ids"]):
            new = table.get(cid) or (GENERIC.get(cid) if d["id"] == "UNIT_MEASURE" else None)
            if not new:
                stripped = SUFFIX.sub("", d["names"][j]).strip()
                new = stripped if stripped and stripped != d["names"][j] else None
            if new and new != d["names"][j]:
                d["names"][j] = new; changed = True; n += 1
    if changed: mp.write_text(json.dumps(meta, separators=(",", ":")))
print(f"editorial labels applied: {n}")
