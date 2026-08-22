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
    # unions and bargaining
    "OECD.ELS.SAE__DF_TUD", "OECD.ELS.SAE__DF_CBC",
    # social provision and inequality
    "OECD.ELS.SPD__DF_SOCX_AGG", "OECD.WISE.INE__DF_IDD",
    # wages
    "OECD.ELS.SAE__GENDER_WAGE_GAP", "OECD.ELS.SAE__PAY_INCIDENCE",
    "OECD.SDD.TPS__DF_HOU_EAR",
    # job quality and precarity
    "OECD.ELS.SAE__DF_TEMP_D", "OECD.ELS.SAE__DF_TEMP_I_GEN",
    "OECD.ELS.SAE__DF_INVPT_I", "OECD.ELS.SAE__DF_FTPT_COMMON_INC",
    "OECD.ELS.SAE__DF_AVG_USL_WK_WKD", "OECD.ELS.JAI__DF_HOURSPOV",
    # unemployment and participation
    "OECD.ELS.SAE__DF_DUR_D", "OECD.ELS.SAE__DF_DUR_I",
    "OECD.SDD.TPS__DF_IALFS_EMP_WAP_Q", "OECD.SDD.TPS__DF_IALFS_OLF_WAP_Q",
    "OECD.EDU.IMEP__DF_LSO_TRANS_MIGR",
    # the state
    "OECD.CTP.TPS__DF_TW_COMP", "OECD.CTP.TPS__DF_RSGLOBAL",
    "OECD.GOV.GIP__DF_GOV_SPS_2023",
    # migration
    "OECD.ELS.IMD__DF_MIG_EMP_EDU", "OECD.ELS.IMD__DF_MIG_NUP_SEX",
]
# datasets folded into others, or judged not worth carrying
RETIRED = {
    "OECD.EDU.IMEP__DF_LSO_EARN_REL_MALE", "OECD.ELS.SPD__DF_NET_GDP",
    "OECD.SDD.NAD__DF_TABLE2_B6_VPVOP", "OECD.SDD.NAD__DF_TABLE2_B5N_HVPVOB",
    "OECD.SDD.TPS__DF_ALFS_EMP_ICSE93", "OECD.ELS.SPD__DF_PUB_FAM",
    "OECD.ELS.SPD__DF_PUB_DIS_SIC", "OECD.ELS.SPD__DF_PUB_PRV",
    "OECD.ELS.SAE__DF_FTPT",
}
RENAME = {
    "OECD.WISE.INE__DF_IDD": "Income inequality and poverty",
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
    flows.append(f)
cat["flows"] = flows

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
