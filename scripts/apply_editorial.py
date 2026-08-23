#!/usr/bin/env python3
"""Editorial decisions about the catalog, re-applied after any rebuild.

Which countries lead, which datasets lead, and the country-name lookup. These
are judgements, not derivable from the source, so they must survive a
regeneration rather than living only in the built file.
"""
import json, pathlib

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"

SAMPLE = ["DEU", "DNK", "SWE", "NLD", "FRA", "GBR", "USA"]
CORE = SAMPLE + ["NOR", "FIN", "AUT", "ESP", "ITA", "CAN",
                 "BEL", "ISL", "NZL", "EU27", "EU27_2020", "OECD", "OECD_REP"]
FEATURED = [
    # The lead tier answers the questions the research is actually about, and
    # stays small enough to read in one pass. Everything else is one click away
    # under "Additional topics".

    # institutions: who sets the terms of work
    "OECD.ELS.SAE__DF_TUD", "OECD.ELS.SAE__DF_CBC",
    "OECD.ELS.JAI__DF_EPL", "OECD.ELS.SAE__RMW", "OECD_AIAS__ICTWSS", "VDEM__CIVIL_SOCIETY", "ILO__STRIKES",
    # what work pays, and how unequally
    "OECD.ELS.SAE__GENDER_WAGE_GAP", "OECD.ELS.SAE__PAY_INCIDENCE",
    "OECD.ELS.SAE__DEC_I", "OWID__LABOR_SHARE",
    # concentration
    "OECD.WISE.INE__DF_IDD", "WID_LIS__DF_CONCENTRATION",
    # what work is like
    "OECD.ELS.SAE__DF_TEMP_D", "OECD.ELS.SAE__DF_INVPT_I",
    "OECD.ELS.SAE__DF_AVG_USL_WK_WKD", "OWID__WORKING_HOURS_LONGRUN",
    # who works and who does not
    "OECD.SDD.TPS__DF_IALFS_EMP_WAP_Q", "OECD.SDD.TPS__DF_IALFS_OLF_WAP_Q",
    "OECD.SDD.TPS__DF_IALFS_LF_WAP_Q", "OECD.ELS.SAE__DF_TENURE_AVE",
    "OECD.ELS.JAI__DF_LMP",
    "OECD.ELS.SAE__DF_DUR_D",
    # what the state provides
    "OECD.ELS.SPD__DF_SOCX_AGG", "OWID__SOCIAL_SPENDING_LONGRUN",
    "OECD.ELS.JAI__DF_NRR",
    # what the state takes
    "OECD.CTP.TPS__DF_TW_COMP", "OECD.CTP.TPS__DF_RSGLOBAL",
]
# datasets folded into others, or judged not worth carrying
RETIRED = {
    "OECD.EDU.IMEP__DF_LSO_EARN_REL_MALE", "OECD.ELS.SPD__DF_NET_GDP",
    "OECD.SDD.NAD__DF_TABLE2_B6_VPVOP", "OECD.SDD.NAD__DF_TABLE2_B5N_HVPVOB",
    "OECD.SDD.TPS__DF_ALFS_EMP_ICSE93", "OECD.ELS.SPD__DF_PUB_FAM",
    "OECD.ELS.SPD__DF_PUB_DIS_SIC", "OECD.ELS.SPD__DF_PUB_PRV",
    "OECD.ELS.SAE__DF_FTPT",
}

# ---------------------------------------------------------------------------
# Topics. OECD's own taxonomy files these by collecting department, which puts
# immigrants' labor market outcomes under Society and has no place at all for
# inequality. This is organised around the questions instead.
TOPICS = [
    ("UNION", "Labor market institutions"),
    ("WAGE",  "Wages and earnings"),
    ("INEQ",  "Inequality and poverty"),
    ("JOBS",  "Jobs and job quality"),
    ("UNEMP", "Unemployment and participation"),
    ("MIGR",  "Migration and labor markets"),
    ("SOCIAL","Social protection and pensions"),
    ("TAX",   "Taxation and the state"),
    ("EDU",   "Education and skills"),
    ("ECON",  "Economy and productivity"),
    ("DIGI",  "Digital"),
]
TOPIC_OF = {
    "OECD.ELS.SAE__DF_TUD": "UNION", "OECD.ELS.SAE__DF_CBC": "UNION",
    "OECD.ELS.JAI__DF_EPL": "UNION", "OECD.ELS.SAE__RMW": "UNION",

    "OECD.SDD.TPS__DF_HOU_EAR": "WAGE",
    # dispersion and between-group gaps are inequality, not wage levels
    "OECD.ELS.SAE__DEC_I": "INEQ", "OECD.ELS.SAE__PAY_INCIDENCE": "INEQ",
    "OECD.ELS.SAE__GENDER_WAGE_GAP": "INEQ",
    "OECD.EDU.IMEP__DF_LSO_EARN_ALL": "WAGE",
    "OECD.ELS.JAI__DF_HOURSPOV": "WAGE",

    "OECD.WISE.INE__DF_IDD": "INEQ", "WID_LIS__DF_CONCENTRATION": "INEQ",
    "OECD.ELS.SPD__DF_IPOP": "INEQ", "OECD.ELS.JAI__DF_HOURSPOV": "INEQ",
    "ESTAT__DF_INWORK_POV": "INEQ", "EPI__DF_US_PAY_POWER": "WAGE",
    "OII_OLI__DF_ONLINE_GIG": "JOBS", "ESTAT__DF_DEPRIVATION": "INEQ",

    "OECD.ELS.SAE__DF_TEMP_D": "JOBS", "OECD.ELS.SAE__DF_TEMP_I_GEN": "JOBS",
    "OECD.ELS.SAE__DF_INVPT_I": "JOBS", "OECD.ELS.SAE__DF_FTPT_COMMON": "JOBS",
    "OECD.ELS.SAE__DF_FTPT_COMMON_INC": "JOBS", "OECD.ELS.SAE__DF_FTPT_INC_GEN": "JOBS",
    "OECD.ELS.SAE__DF_AVG_USL_WK_WKD": "JOBS",
    "OECD.SDD.TPS__DF_ALFS_EMP": "JOBS", "OECD.SDD.TPS__DF_IALFS_EMP_ISIC4_Q": "JOBS",
    "OECD.SDD.TPS__DF_SUMTAB": "JOBS",

    "OECD.SDD.TPS__DF_IALFS_EMP_WAP_Q": "UNEMP",
    "OECD.SDD.TPS__DF_IALFS_OLF_WAP_Q": "UNEMP",
    "OECD.ELS.SAE__DF_DUR_D": "UNEMP", "OECD.ELS.SAE__DF_DUR_I": "UNEMP",
    "OECD.ELS.SAE__DF_AVD_DUR": "UNEMP",

    "OECD.ELS.IMD__DF_MIG_EMP_EDU": "MIGR", "OECD.ELS.IMD__DF_MIG_NUP_SEX": "MIGR",
    "OECD.EDU.IMEP__DF_LSO_NEAC_INAC_MIGR": "MIGR",
    "OECD.EDU.IMEP__DF_LSO_NEAC_UNEMP_MIGR": "MIGR",
    "OECD.EDU.IMEP__DF_LSO_TRANS_MIGR": "MIGR",

    "OECD.ELS.SPD__DF_SOCX_AGG": "SOCIAL", "OECD.ELS.SPD__DF_DPS": "SOCIAL",
    "OECD.ELS.JAI__DF_NRR": "SOCIAL", "OECD.ELS.JAI__DF_HGRR": "SOCIAL",
    "OECD.ELS.JAI__DF_IA": "SOCIAL", "OECD.ELS.SPD__DF_PRR": "SOCIAL",
    "OECD.ELS.JAI__DF_SBE": "UNION",
    "OWID__LABOR_RIGHTS": "UNION",
    "OECD_AIAS__ICTWSS": "UNION",
    "VDEM__CIVIL_SOCIETY": "UNION",
    "ILO__STRIKES": "UNION",
    "OWID__LABOR_SHARE": "INEQ",
    "OECD.GOV.GIP__DF_GOV_EMPPS_REP_2025": "TAX",
    "OECD.ELS.SAE__DF_TENURE_AVE": "JOBS",
    "OECD.ELS.JAI__DF_LMP": "SOCIAL",
    "OECD.SDD.TPS__DF_IALFS_LF_WAP_Q": "UNEMP",
    "OWID__WORKING_HOURS_LONGRUN": "JOBS",
    "OWID__SOCIAL_SPENDING_LONGRUN": "SOCIAL",
    "OECD.ELS.SPD__DF_PW": "SOCIAL",

    "OECD.CTP.TPS__DF_TW_COMP": "TAX", "OECD.CTP.TPS__DF_RSGLOBAL": "TAX",
    "OECD.GOV.GIP__DF_GOV_SPS_2023": "TAX",

    "OECD.EDU.IMEP__DF_UOE_NF_PERS_CLS": "EDU",
    "OECD.EDU.IMEP__DF_UOE_NF_DIST_VET": "EDU",

    "OECD.SDD.TPS__DF_PDB": "ECON", "OECD.SDD.NAD__DF_TABLE2": "ECON",
    "OECD.SDD.NAD__DF_TABLE9A": "ECON", "OECD.SDD.NAD__DF_TABLE5_T501": "ECON",

    "OECD.STI.DEP__DF_HH": "DIGI", "OECD.STI.DEP__DF_IND": "DIGI",
}

RENAME = {
    "OECD.WISE.INE__DF_IDD": "Income inequality and poverty",
    "OECD.ELS.JAI__DF_EPL": "Employment protection strictness",
    "OECD.ELS.SAE__RMW": "Minimum wages",
    "OECD.ELS.JAI__DF_NRR": "Unemployment benefit replacement rates",
    "OECD.ELS.JAI__DF_PTRUB": "What taking a job costs you",
    "OECD.ELS.JAI__DF_HGRR": "Unemployment benefit replacement rates, 1961-2005",
    "OECD.ELS.SAE__DEC_I": "Earnings dispersion (full-time employees)",
    "WID_LIS__DF_CONCENTRATION": "Inequality measures",
    "OECD.ELS.JAI__DF_SBE": "Strictness of activation requirements",
    "OECD.ELS.JAI__DF_IA": "Adequacy of minimum income benefits",
    "OECD.ELS.SPD__DF_PRR": "Pension replacement rates",
    "OECD.GOV.GIP__DF_GOV_EMPPS_REP_2025": "Public employment and representation",
    "OECD.ELS.SAE__DF_TENURE_AVE": "Average job tenure",
    "OECD.ELS.JAI__DF_LMP": "Labor market programme spending",
    "OECD.SDD.TPS__DF_IALFS_LF_WAP_Q": "Labor force participation rate",
}

p = SITE/"catalog.json"
cat = json.loads(p.read_text())
prior = {f["slug"]: f for f in cat.get("flows", [])}
# The payloads on disk are the truth. Rebuilding the list from them means a
# regenerated catalog can never silently drop a published dataset.
on_disk = sorted(d.name for d in (SITE/"flows").iterdir() if d.is_dir())
flows = []
for slug in on_disk:
    if slug in RETIRED: continue
    m = json.loads((SITE/"flows"/slug/"meta.json").read_text())
    f = dict(prior.get(slug, {}))
    f.update({
        "slug": slug, "id": m.get("id", slug), "agency": m.get("agency", ""),
        "topic": m.get("topic"), "source_url": m.get("source_url", ""),
        "description": (m.get("desc_text") or "")[:600],
        "periods": [m["periods"][0], m["periods"][-1]] if m.get("periods") else None,
        "layout": m.get("layout"),
        "name": RENAME.get(slug, m["name"]),
        "featured": slug in FEATURED,
        "n_series": m["n_series"], "n_obs": m["n_obs"],
    })
    if m.get("derived_units"): f["derived"] = list(m["derived_units"])
    if m.get("coverage"): f["sample_missing"] = m["coverage"].get("sample_missing", [])
    f["topic"] = TOPIC_OF.get(slug, "ECON")
    # the dataset page reads its own metadata, so topic and title live there too
    if m.get("topic") != f["topic"] or m.get("name") != f["name"]:
        m["topic"] = f["topic"]; m["name"] = f["name"]
        (SITE/"flows"/slug/"meta.json").write_text(json.dumps(m, separators=(",", ":")))
    flows.append(f)
cat["flows"] = flows

cat["topic_tree"] = {"id": "TOPICS", "name": "Topics",
                     "categories": [{"id": i, "name": n} for i, n in TOPICS]}
unplaced = [f["slug"] for f in flows if f["slug"] not in TOPIC_OF]
if unplaced: print(f"warning: {len(unplaced)} datasets have no topic: {unplaced}")

cat["default_countries"] = SAMPLE
cat["sample_countries"] = SAMPLE
cat["core_areas"] = CORE
cat["featured_order"] = [s for s in FEATURED if any(f["slug"] == s for f in cat["flows"])]

names = {}
for f in cat["flows"]:
    m = json.loads((SITE/"flows"/f["slug"]/"meta.json").read_text())
    d = next((x for x in m["dims"] if x["id"] == "REF_AREA"), None)
    if not d: continue
    for c, n in zip(d["ids"], d["names"]):
        if c not in names and n and n != c: names[c] = n
cat["area_names"] = {c: names[c] for c in sorted(names)}

p.write_text(json.dumps(cat, separators=(",", ":")))
print(f'datasets {len(cat["flows"])}  featured {sum(1 for f in cat["flows"] if f["featured"])}'
      f'  observations {sum(f["n_obs"] for f in cat["flows"]):,}')
