#!/usr/bin/env python3
"""Pay, productivity and union power in the United States, from EPI.

The Economic Policy Institute's State of Working America Data Library holds
several series that have no cross-national equivalent and that OECD does not
publish at all: the union wage premium, the gap between productivity and pay
since 1948, the CEO-to-worker pay ratio since 1965, and the share of all wages
taken by each slice of the distribution back to 1937.

This is a United States dataset. It is here because the questions it answers --
does a union raise your pay, did pay follow productivity, who took the gains --
cannot be asked of the cross-national tables.
"""
import csv, gzip, json, pathlib, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
RAW  = ROOT/"data/raw/epi"
SLUG = "EPI__DF_US_PAY_POWER"

# file -> [(source measure, code, display name, unit code)]
WANT = {
 "historical_union_membership": [
   ("Share in a union", "UNION_MEM", "Union membership rate", "PT")],
 "union_wage_premium": [
   ("Union wage premium, average (regression-based)", "UNION_PREM",
    "Union wage premium", "PT_PREM")],
 "productivity_and_pay_indexes": [
   ("Productivity and pay real index, base = 1948", "PROD_IX",
    "Productivity and pay, index (1948 = 100)", "IX48")],
 "productivity_and_pay_levels": [
   ("Productivity and pay, real dollars per hour (2025$)", "PROD_LVL",
    "Productivity and pay, real dollars per hour", "USD_HR")],
 "ceo_pay_ratio": [
   ("CEO-to-worker pay ratio, realized", "CEO_REAL",
    "CEO-to-worker pay ratio (pay actually realized)", "RATIO"),
   ("CEO-to-worker pay ratio, granted", "CEO_GRANT",
    "CEO-to-worker pay ratio (pay as granted)", "RATIO"),
   ("Ratio of CEO compensation to top 0.1% wages", "CEO_TOP01",
    "CEO pay relative to the top 0.1 per cent", "RATIO")],
 "annual_wages_for_select_wage_groups": [
   ("Share of total annual earnings", "EARN_SHARE",
    "Share of all wages taken by this group", "PT"),
   ("Average real annual wage (2023$)", "WAGE_REAL",
    "Average annual wage, inflation adjusted", "USD")],
 "college_wage_premium": [
   ("College wage premium, average", "COLLEGE_PREM",
    "College wage premium", "PT_PREM")],
 "gender_wage_gap": [
   ("Gender wage gap, raw median", "GAP_SEX",
    "Gender wage gap (median)", "PT_PREM")],
 "black_white_wage_gap": [
   ("Black-white wage gap, raw median", "GAP_BW",
    "Black-white wage gap (median)", "PT_PREM")],
 "hispanic_white_wage_gap": [
   ("Hispanic-white wage gap, raw median", "GAP_HW",
    "Hispanic-white wage gap (median)", "PT_PREM")],
 "minimum_wage": [
   ("Real minimum wage (2025$)", "MINWAGE",
    "Federal minimum wage, inflation adjusted", "USD_HR")],
}

# EPI group_value -> (breakdown code, display name)
GRP = {
 "": ("_T", "Overall"), "Overall": ("_T", "Overall"), "All": ("_T", "Overall"),
 "Net productivity (output per hour)": ("PRODY", "Productivity (output per hour)"),
 "Total compensation per hour": ("COMPY", "Pay (compensation per hour)"),
 "Bottom 90%": ("B90", "Bottom 90 per cent"),
 "90–95th percentiles": ("P90_95", "90th to 95th percentile"),
 "95–99th percentiles": ("P95_99", "95th to 99th percentile"),
 "99.0–99.9th percentiles": ("P99_999", "99th to 99.9th percentile"),
 "Top 0.1%": ("TOP01", "Top 0.1 per cent"),
 "Top 1%": ("TOP1", "Top 1 per cent"),
 "Top 5%": ("TOP5", "Top 5 per cent"),
 "Top 10%": ("TOP10", "Top 10 per cent"),
 "90–99th percentiles": ("P90_99", "90th to 99th percentile"),
 "Male": ("M", "Men"), "Female": ("F", "Women"),
 "White": ("WHITE", "White"), "Black": ("BLACK", "Black"),
 "Hispanic": ("HISP", "Hispanic"),
 "Asian American/Pacific Islander": ("AAPI", "Asian American / Pacific Islander"),
 "Less than high school": ("ED_LTHS", "Left school before high school"),
 "High school": ("ED_HS", "High school"),
 "Some college": ("ED_SC", "Some college"),
 "College": ("ED_COL", "College degree"),
 "Bachelor's degree": ("ED_BA", "Bachelor's degree"),
 "Advanced degree": ("ED_ADV", "Advanced degree"),
}
ORDER = ["_T", "PRODY", "COMPY", "B90", "P90_95", "P95_99", "P99_999", "P90_99",
         "TOP10", "TOP5", "TOP1", "TOP01", "M", "F", "WHITE", "BLACK", "HISP",
         "AAPI", "ED_LTHS", "ED_HS", "ED_SC", "ED_BA", "ED_COL", "ED_ADV"]
UNITS = [("PT", "Percentage"), ("PT_PREM", "Percentage difference in pay"),
         ("IX48", "Index, 1948 = 100"), ("USD_HR", "Dollars per hour"),
         ("USD", "Dollars per year"), ("RATIO", "Ratio")]

rec = {}; seen_grp = set(); unknown = collections.Counter()
for stem, wants in WANT.items():
    f = RAW/f"{stem}.csv"
    if not f.exists(): print(f"  MISSING {stem}"); continue
    by = {m[0]: m for m in wants}
    n = 0
    for r in csv.DictReader(open(f)):
        if r["geo_type"] != "national" or r["date_interval"] != "year": continue
        if r["value"] in ("", "NA") or r["measure"] not in by: continue
        gv = (r.get("group_value") or "").strip()
        if gv not in GRP: unknown[gv] += 1; continue
        g = GRP[gv][0]
        try: v = float(r["value"])
        except ValueError: continue
        _, code, _, unit = by[r["measure"]]
        # EPI stores rates and premiums as fractions; the site shows percentages
        if unit in ("PT", "PT_PREM"): v *= 100
        rec.setdefault(("USA", code, g, unit), {})[r["year"]] = v
        seen_grp.add(g); n += 1
    print(f"  {stem:42} {n:>6} observations")
if unknown: print("  unmapped groups:", dict(unknown.most_common(8)))

GNAME = {}
for _code, _nm in GRP.values(): GNAME.setdefault(_code, _nm)

MEAS = [(c, n, u) for w in WANT.values() for _, c, n, u in w]
groups = [g for g in ORDER if g in seen_grp]
periods = sorted({y for s in rec.values() for y in s}, key=int)
ai = {"USA": 0}; mi = {m[0]: i for i, m in enumerate(MEAS)}
gi = {g: i for i, g in enumerate(groups)}; ui = {u[0]: i for i, u in enumerate(UNITS)}
pi = {y: i for i, y in enumerate(periods)}

payload = []
for (a, m, g, u), s in rec.items():
    ys = sorted(s, key=int)
    payload.append({"k": [ai[a], mi[m], gi[g], ui[u]],
                    "t": [pi[y] for y in ys], "v": [round(s[y], 4) for y in ys]})

meta = {
 "slug": SLUG, "id": "DF_US_PAY_POWER", "agency": "Economic Policy Institute",
 "version": "1.0", "name": "Pay, productivity and union power (United States)",
 "description": "",
 "desc_html": (
   "A United States dataset, here because the questions it answers cannot be asked of "
   "the cross-national tables.<br>"
   "<b>Did pay follow productivity?</b> Set the indicator to the 1948 index and compare "
   "productivity against compensation per hour. They rise together until the early "
   "1970s and then separate, and the space between the two lines is the return on work "
   "that did not reach the people doing it.<br>"
   "<b>Does a union raise your pay?</b> The union wage premium is what a union member "
   "earns above an otherwise comparable non-member -- same industry, occupation, "
   "education, region -- so it is not a comparison of union jobs with all jobs. It can "
   "be read by race, sex and education, and it is largest for the workers with least "
   "bargaining power on their own. Alongside it, union membership runs back to 1917, "
   "which covers the whole rise and fall.<br>"
   "<b>Who took the gains?</b> The share of all wages going to each slice of the "
   "distribution runs back to 1937, separating the top 0.1 per cent from the merely "
   "well paid. The CEO-to-worker pay ratio runs from 1965, in two versions: pay as "
   "granted, and pay as actually realized when options are exercised.<br>"
   "Source: Economic Policy Institute, "
   "<a href=\"https://data.epi.org/\" target=\"_blank\" rel=\"noopener noreferrer\">State "
   "of Working America Data Library</a>."),
 "desc_text": "US union wage premium, union membership since 1917, productivity against "
   "pay since 1948, the CEO-to-worker pay ratio since 1965, and the share of all wages "
   "taken by each part of the distribution since 1937.",
 "topic": "SOC.SOC_INE",
 "dims": [
   {"id": "REF_AREA", "name": "Country", "ids": ["USA"], "names": ["United States"]},
   {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in MEAS],
    "names": [m[1] for m in MEAS], "default": 2},
   {"id": "BREAKDOWN", "name": "Breakdown", "ids": groups,
    "names": [GNAME[g] for g in groups],
    "default": 0},
   {"id": "UNIT_MEASURE", "name": "Measured as", "ids": [u[0] for u in UNITS],
    "names": [u[1] for u in UNITS]},
 ],
 "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
 # one country, so the chart compares breakdowns rather than countries
 "area_dim": None, "layout": "single",
 "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
 "source_url": "https://data.epi.org/",
 "hidden_dims": {},
 "source_notes": [
   "Not an OECD table. Economic Policy Institute, State of Working America Data Library, "
   "built mainly from Current Population Survey microdata.",
   "The union wage premium is regression-adjusted: it compares union members with "
   "non-members of the same education, experience, occupation, industry, region, race "
   "and sex, so it is an estimate of what the union itself is worth rather than a raw "
   "comparison of union and non-union jobs.",
   "Productivity here is net productivity -- output per hour after depreciation -- and "
   "pay is total compensation per hour including benefits, both deflated to the same "
   "base. Using net productivity and total compensation is the conservative choice; it "
   "makes the gap smaller than the commonly quoted version.",
   "Wage-group shares come from Social Security Administration earnings records, which "
   "cover wage and salary income only. Capital gains and business income are not in "
   "them, so top shares here are lower than income-based measures such as WID's.",
 ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f'\n{len(payload)} series, {meta["n_obs"]:,} observations, {periods[0]}-{periods[-1]}')
