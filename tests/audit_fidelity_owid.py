#!/usr/bin/env python3
"""Re-download every Our World in Data grapher behind a dataset and compare.

Five datasets are built from OWID's harmonised exports. OWID revises: it adopts
new source vintages and re-harmonises country names. A dataset built months ago
can drift without anything on the site changing, so the comparison is against a
fresh pull of the same grapher slugs.
"""
import csv, gzip, io, json, pathlib, re, urllib.request, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
BASE = "https://ourworldindata.org/grapher/{}.csv?csvType=full&useColumnShortNames=true"

def fetch(slug):
    req = urllib.request.Request(BASE.format(slug),
        headers={"User-Agent": "ForestAndTheTrees/1.0 (personal research site)"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8", "replace"))))

def load(slug):
    d = ROOT/"site/data/flows"/slug
    m = json.loads((d/"meta.json").read_text())
    r = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
    return m, r

def site_index(slug, measure_dim="MEASURE"):
    m, recs = load(slug)
    ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
    ai = ids.index("REF_AREA")
    mi = next((i for i, x in enumerate(m["dims"]) if x["id"] == measure_dim), None)
    out = {}
    for r in recs:
        a = D["REF_AREA"]["ids"][r["k"][ai]]
        c = D[measure_dim]["ids"][r["k"][mi]] if mi is not None else ""
        for t, v in zip(r["t"], r["v"]): out[(a, c, P[t])] = v
    return out, set(D["REF_AREA"]["ids"])

# slug on the site -> [(grapher, column, measure code, scale)]
JOBS = {
 "WID_LIS__DF_CONCENTRATION": [
   ("gini-coefficient-wid","gini__welfare_type_before_tax__extrapolated_no","GINI_PRETAX",1),
   ("gini-coefficient-lis","gini__welfare_type_dhi__equivalence_scale_square_root","GINI_DHI",1),
   ("income-share-top-1-before-tax-wid-extrapolations",
    "share_top_1__welfare_type_before_tax__extrapolated_no","TOP1_INC",1),
   ("wealth-share-richest","share_top_1__welfare_type_wealth__extrapolated_no","TOP1_WEALTH",1),
   ("palma-ratio-wid","palma_ratio__welfare_type_before_tax__extrapolated_no","PALMA",1),
   ("income-inequality-atkinson-index-undp","ineq_inc","ATKINSON",1),
   ("gini-coefficient-equivalized-income-chartbook",
    "gini_coefficient__equivalized_income_after_tax_and_transfers","GINI_LONGRUN",1),
   ("gini-coefficient-wb",
    "gini__welfare_type_income_or_consumption__table_income_or_consumption_consolidated"
    "__survey_comparability_no_spells","GINI_WB",1),
   ("relative-poverty-share-of-people-below-40-of-the-median",
    "headcount_ratio__ppp_version_2021__poverty_line_40pct_of_the_median"
    "__welfare_type_income_or_consumption__table_income_or_consumption_consolidated"
    "__survey_comparability_no_spells","POV40",1)],
 "OWID__WORKING_HOURS_LONGRUN": [
   ("annual-working-hours-per-worker","working_hours_omm","HOURS",1)],
 "OWID__SOCIAL_SPENDING_LONGRUN": [
   ("social-spending-oecd-longrun","share_gdp","SOCX",1)],
 "OWID__LABOR_RIGHTS": [
   ("level-of-national-compliance-with-labor-rights","_8_8_2__sl_lbr_ntlcpl","RIGHTS",1)],
 "VDEM__CIVIL_SOCIETY": [
   ("freedom-of-association-index","freeassoc_vdem__estimate_best","FREEASSOC",1),
   ("civil-society-participation-index","civsoc_particip_vdem__estimate_best","CIVPART",1),
   ("strong-civil-society-index","civ_soc_str_vdem__estimate_best","CIVSTR",1),
   ("egalitarian-democracy-index-vdem","egaldem_vdem__estimate_best","EGALDEM",1)],
}
total_m = total_x = 0
for slug, jobs in JOBS.items():
    ours, areas = site_index(slug)
    for grapher, col, code, scale in jobs:
        try: rows = fetch(grapher)
        except Exception as e:
            print(f"  {code:14} fetch failed: {type(e).__name__}"); continue
        n = x = 0; ex = []
        for r in rows:
            a = (r.get("code") or "").strip()
            if not re.fullmatch(r"[A-Z]{3}", a) or a not in areas: continue
            raw = (r.get(col) or "").strip()
            if not raw: continue
            try: v = float(raw)*scale
            except ValueError: continue
            got = ours.get((a, code, r["year"]))
            if got is None: continue
            n += 1
            if abs(got - v) > max(1e-6, abs(v)*1e-9):
                x += 1
                if len(ex) < 3: ex.append((a, r["year"], v, got))
        print(f"  {code:14} compared {n:>6,}  mismatched {x}")
        for e in ex: print("       ", e)
        total_m += n - x; total_x += x
print(f"\nOWID-sourced: matched {total_m:,}  mismatched {total_x}")
