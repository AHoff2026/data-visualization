#!/usr/bin/env python3
"""Build one dataset from Our World in Data's grapher exports.

OWID republishes the World Inequality Database and the Luxembourg Income Study
in a harmonised country-year form. Top income shares and wealth shares do not
exist in OECD's statistics at all, and they are the outcome measures the social
spending tables cannot speak to.

Only non-extrapolated columns are used: no modelled or projected values.
"""
import csv, gzip, json, pathlib, re, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SLUG = "WID_LIS__DF_CONCENTRATION"

# chart slug -> (column, measure code, measure name, unit code, unit name, source)
SERIES = [
    # Gini, from four sources that do not measure the same thing. Which income
    # concept a Gini uses changes it by more than most cross-country gaps, so
    # they are kept apart rather than spliced.
    ("gini-coefficient-wid", "gini__welfare_type_before_tax__extrapolated_no",
     "GINI_PRETAX", "Gini, income before tax", "IX01", "0 to 1",
     "World Inequality Database"),
    ("gini-coefficient-lis", "gini__welfare_type_dhi__equivalence_scale_square_root",
     "GINI_DHI", "Gini, disposable household income", "IX01", "0 to 1",
     "Luxembourg Income Study"),
    ("gini-coefficient-wb",
     "gini__welfare_type_income_or_consumption__table_income_or_consumption_consolidated"
     "__survey_comparability_no_spells",
     "GINI_WB", "Gini, income or consumption surveys", "IX01", "0 to 1",
     "World Bank PIP"),
    ("gini-coefficient-equivalized-income-chartbook",
     "gini_coefficient__equivalized_income_after_tax_and_transfers",
     "GINI_LONGRUN", "Gini, equivalized income after tax and transfers, since 1901",
     "IX01", "0 to 1", "Chartbook of Economic Inequality"),
    # concentration at the top
    ("income-share-top-1-before-tax-wid-extrapolations",
     "share_top_1__welfare_type_before_tax__extrapolated_no",
     "TOP1_INC", "Income share of the top 1 per cent, before tax",
     "PT", "Percentage of national income", "World Inequality Database"),
    ("wealth-share-richest", "share_top_1__welfare_type_wealth__extrapolated_no",
     "TOP1_WEALTH", "Wealth share of the top 1 per cent",
     "PT", "Percentage of national wealth", "World Inequality Database"),
    # spread across the distribution
    ("palma-ratio-wid", "palma_ratio__welfare_type_before_tax__extrapolated_no",
     "PALMA", "Palma ratio: top 10 per cent over bottom 40 per cent",
     "RATIO", "Ratio", "World Inequality Database"),
    ("income-inequality-atkinson-index-undp", "ineq_inc",
     "ATKINSON", "Atkinson index of income inequality", "IX", "Index",
     "UNDP Human Development Report"),
    # poverty measured against the national median rather than a dollar line
    ("relative-poverty-share-of-people-below-40-of-the-median",
     "headcount_ratio__ppp_version_2021__poverty_line_40pct_of_the_median"
     "__welfare_type_income_or_consumption__table_income_or_consumption_consolidated"
     "__survey_comparability_no_spells",
     "POV40", "Share below 40 per cent of median income",
     "PT_POP", "Percentage of population", "World Bank PIP"),
]
BASE = "https://ourworldindata.org/grapher/{}.csv?csvType=full&useColumnShortNames=true"

def fetch(slug):
    req = urllib.request.Request(BASE.format(slug),
        headers={"User-Agent": "ForestAndTheTrees/1.0 (personal research site)"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return list(csv.DictReader(r.read().decode("utf-8").splitlines()))

areas, measures, units = {}, [], []
records = {}          # (area, measure, unit) -> {year: value}
names = {}
sources = {}
for slug, col, mcode, mname, ucode, uname, src in SERIES:
    rows = fetch(slug)
    if mcode not in [m[0] for m in measures]: measures.append((mcode, mname))
    if ucode not in [u[0] for u in units]: units.append((ucode, uname))
    sources[mname] = src
    kept = 0
    for r in rows:
        code = (r.get("code") or "").strip()
        # ISO3 only: OWID aggregates carry OWID_ prefixes and regional labels
        if not re.fullmatch(r"[A-Z]{3}", code): continue
        v = (r.get(col) or "").strip()
        if not v: continue
        try: val = float(v)
        except ValueError: continue
        names.setdefault(code, r["entity"])
        records.setdefault((code, mcode, ucode), {})[r["year"]] = val
        kept += 1
    print(f"  {slug:52} {kept:7} observations")

area_ids = sorted(names)
periods = sorted({y for d in records.values() for y in d}, key=int)
pidx = {y: i for i, y in enumerate(periods)}
aidx = {a: i for i, a in enumerate(area_ids)}
midx = {m[0]: i for i, m in enumerate(measures)}
uidx = {u[0]: i for i, u in enumerate(units)}

payload = []
for (a, m, u), series in records.items():
    ys = sorted(series, key=int)
    payload.append({"k": [aidx[a], midx[m], uidx[u]],
                    "t": [pidx[y] for y in ys],
                    "v": [round(series[y], 6) for y in ys]})

meta = {
    "slug": SLUG, "id": "DF_CONCENTRATION", "agency": "WID / LIS", "version": "1.0",
    "name": "Inequality measures",
    "description": "",
    "desc_html": ("Inequality measured several ways, because the way it is measured "
        "decides the answer. Four Gini coefficients from four sources that do not use "
        "the same income concept; the share of income and of wealth held by the top one "
        "per cent; the Palma ratio; the Atkinson index; and relative poverty against the "
        "national median.<br>A Gini of pre-tax income and a Gini of disposable income "
        "are different objects, and the gap between them is the redistribution a state "
        "performs. They are kept apart here rather than spliced into one line.<br>Sources: "
        "<a href=\"https://wid.world/\" target=\"_blank\" rel=\"noopener noreferrer\">World "
        "Inequality Database</a>, and the Gini coefficient of disposable household income "
        "from the <a href=\"https://www.lisdatacenter.org/\" target=\"_blank\" "
        "rel=\"noopener noreferrer\">Luxembourg Income Study</a>, as republished by Our "
        "World in Data.<br>These are the concentration measures OECD does not publish: how "
        "much of national income and of national wealth the richest one per cent hold. "
        "Only observed values are included; OWID's extrapolated and projected columns are "
        "not used."),
    "desc_text": "Top income and wealth shares from the World Inequality Database and the "
        "Gini coefficient of disposable household income from the Luxembourg Income Study, "
        "as republished by Our World in Data.",
    "topic": "SOC.SOC_INE",
    "dims": [
        {"id": "REF_AREA", "name": "Country",
         "ids": area_ids, "names": [names[a] for a in area_ids]},
        {"id": "MEASURE", "name": "Indicator",
         "ids": [m[0] for m in measures], "names": [m[1] for m in measures]},
        {"id": "UNIT_MEASURE", "name": "Measured as",
         "ids": [u[0] for u in units], "names": [u[1] for u in units]},
    ],
    "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
    "area_dim": "REF_AREA", "layout": "single",
    "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
    "source_url": "https://ourworldindata.org/economic-inequality",
    "hidden_dims": {},
    "source_notes": [
        "Not an OECD table. " + "; ".join(f"{k} — {v}" for k, v in sources.items()) +
        ", via Our World in Data. Only observed values are used: OWID's extrapolated and "
        "projected columns are excluded, so the series show what was measured rather than "
        "what was modelled.",
    ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(
    json.dumps(payload, separators=(",", ":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f'\n{meta["n_series"]} series, {meta["n_obs"]:,} observations, '
      f'{len(area_ids)} countries, {periods[0]}-{periods[-1]}')
