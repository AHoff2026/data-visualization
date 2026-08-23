#!/usr/bin/env python3
"""Build the labor share dataset from national accounts, ILO and WID.

The headline labor share -- compensation of employees over GDP at market prices --
is the wrong number for comparing countries, for two reasons that pull in
opposite directions and differ enormously by country.

Taxes on production sit in the denominator. A country that raises 25 per cent VAT
has a larger GDP at market prices for the same underlying production, so its
labor share is mechanically smaller. Measuring against income at factor cost
removes the wedge.

Self-employed people earn labor income that the national accounts book as mixed
income, not as compensation of employees. Where self-employment is common the
headline number understates labor's take. Imputing to the self-employed the same
hourly earnings as employees corrects it, and doing that on an hours basis rather
than a headcount basis matters because the self-employed work different hours.

Every combination is exposed separately so the two adjustments can be seen apart.
"""
import csv, gzip, json, pathlib, collections, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SLUG = "OWID__LABOR_SHARE"

MEASURES = [
    # "All workers" counts the self-employed as labor; "employees only" is the raw
    # national accounts number, which books self-employed earnings as profit.
    ("LS_ADJ_HRS_FC",  "Labor share of factor income (all workers, by hours)", "PT_FC"),
    ("LS_FC",       "Labor share of factor income (employees only)", "PT_FC"),
    ("LS_ADJ_HRS_GDP", "Labor share of GDP (all workers, by hours)", "PT_GDP"),
    ("LS_GDP",      "Labor share of GDP (employees only)", "PT_GDP"),
    ("LS_ADJ_PER_FC",  "Labor share of factor income (all workers, by headcount)", "PT_FC"),
    ("CAP_FC",      "Capital and mixed income share of factor income", "PT_FC"),
    ("TAX_GDP",     "Taxes less subsidies on production, share of GDP", "PT_GDP"),
    ("SELF_HRS",    "Self-employed share of hours worked", "PT_HRS"),
    ("LS_ILO",      "Labor share of GDP (ILO, SDG 10.4.1)", "PT_GDP"),
    # within a slice of the distribution
    ("LS_Q_ALL",    "Labor share within income fifth (all workers)", "PT_GRP"),
    ("LS_Q_EMP",    "Labor share within income fifth (employees only)", "PT_GRP"),
    ("PROP_Q",      "Property income share within income fifth", "PT_GRP"),
    ("LS_WID",      "Labor share within percentile group (United States)", "PT_GRP"),
    ("INC_SHARE",   "Group's share of national income", "PT_NI"),
]
UNITS = [
    ("PT_GDP", "Percentage of GDP at market prices"),
    ("PT_FC",  "Percentage of factor income"),
    ("PT_GRP", "Percentage of the group's own income"),
    ("PT_NI",  "Percentage of national income"),
    ("PT_HRS", "Percentage of hours worked"),
]
GROUPS = [
    ("_T",       "Everyone"),
    ("QG1",      "Poorest fifth"),
    ("QG2",      "Second fifth"),
    ("QG3",      "Middle fifth"),
    ("QG4",      "Fourth fifth"),
    ("QG5",      "Richest fifth"),
    ("P0P50",    "Bottom 50 per cent"),
    ("P50P90",   "Middle 40 per cent"),
    ("P0P90",    "Bottom 90 per cent"),
    ("P0P99",    "Bottom 99 per cent"),
    ("P90P100",  "Top 10 per cent"),
    ("P99P100",  "Top 1 per cent"),
]

# The two OECD extracts are large and gitignored; pull them if they are not on disk.
NA_PULLS = [
    ("na_income.csv", "DSD_NAMAIN10@DF_TABLE1_INCOME",
     ".".join(["A", "", "S1", "",
               "B1GQ+D1+D11+D12+B2A3G+B2G+B3G+D2X3+D21X31+P51C",
               "", "", "", "XDC", "V", "", ""])),
    ("na_emp_act.csv", "DSD_NAMAIN10@DF_TABLE3_EMPDC", ".".join(["A"] + [""]*11)),
    ("egdna_inc.csv", "DSD_EGDNA_INC_INC@DF_INC_INC", ".".join(["A"] + [""]*13)),
]
for fname, flow, key in NA_PULLS:
    dest = ROOT/"data/raw"/fname
    if dest.exists(): continue
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = (f"https://sdmx.oecd.org/public/rest/data/OECD.SDD.NAD,{flow},/{key}"
           "?format=csvfilewithlabels")
    print(f"  fetching {fname} ...")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.sdmx.data+csv; charset=utf-8; labels=both",
        "Accept-Encoding": "gzip",
        "User-Agent": "Mozilla/5.0 (Macintosh) DataViz/1.0"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip": raw = gzip.decompress(raw)
    dest.write_bytes(raw)

rec = {}                      # (area, measure, group) -> {year: value}
names = {}
def put(a, m, g, y, v):
    if v is None or not (-1e4 < v < 1e4): return
    rec.setdefault((a, m, g), {})[str(y)] = v

# ---- national accounts -------------------------------------------------
NA = collections.defaultdict(dict)
for r in csv.DictReader(open(ROOT/"data/raw/na_income.csv")):
    if not r["OBS_VALUE"] or r["ACTIVITY"] not in ("_T", "_Z"): continue
    NA[(r["REF_AREA"], r["TIME_PERIOD"])][r["TRANSACTION"]] = float(r["OBS_VALUE"])
    names.setdefault(r["REF_AREA"], r["Reference area"])

EMP = collections.defaultdict(dict)
for r in csv.DictReader(open(ROOT/"data/raw/na_emp_act.csv")):
    if not r["OBS_VALUE"] or r["ACTIVITY"] != "_T": continue
    if r["UNIT_MEASURE"] not in ("H", "PS"): continue
    EMP[(r["REF_AREA"], r["TIME_PERIOD"])][(r["TRANSACTION"], r["UNIT_MEASURE"])] = \
        float(r["OBS_VALUE"])
    names.setdefault(r["REF_AREA"], r["Reference area"])

for (a, y), d in NA.items():
    gdp, coe, tax, cap = d.get("B1GQ"), d.get("D1"), d.get("D2X3"), d.get("B2A3G")
    if not gdp or gdp <= 0: continue
    # Factor income is taken from the income side (compensation plus gross operating
    # surplus and mixed income) rather than as GDP less production taxes. The two differ
    # by the statistical discrepancy, which reaches several per cent of GDP in older
    # years and in a handful of countries; taking the income side makes labor share and
    # capital share sum to exactly 100 and removes the discrepancy from the comparison.
    fc = coe + cap if (coe and cap) else None
    if coe:
        put(a, "LS_GDP", "_T", y, coe/gdp*100)
        if fc and fc > 0: put(a, "LS_FC", "_T", y, coe/fc*100)
    if tax is not None: put(a, "TAX_GDP", "_T", y, tax/gdp*100)
    if cap and fc and fc > 0: put(a, "CAP_FC", "_T", y, cap/fc*100)

    e = EMP.get((a, y), {})
    for unit, tag in (("H", "HRS"), ("PS", "PER")):
        tot, sal = e.get(("EMP", unit)), e.get(("SAL", unit))
        if not (tot and sal and sal > 0 and coe): continue
        adj = coe * tot/sal
        if tag == "HRS":
            put(a, "LS_ADJ_HRS_GDP", "_T", y, adj/gdp*100)
            if fc and fc > 0: put(a, "LS_ADJ_HRS_FC", "_T", y, adj/fc*100)
        elif fc and fc > 0:
            put(a, "LS_ADJ_PER_FC", "_T", y, adj/fc*100)
for (a, y), e in EMP.items():
    tot, slf = e.get(("EMP", "H")), e.get(("SELF", "H"))
    if tot and slf and tot > 0: put(a, "SELF_HRS", "_T", y, slf/tot*100)

# ---- ILO SDG 10.4.1, carried over from the existing payload -------------
old = SITE/"flows"/SLUG
if (old/"meta.json").exists():
    om = json.loads((old/"meta.json").read_text())
    orecs = json.loads(gzip.decompress((old/"all.json.gz").read_bytes()))
    oa = om["dims"][0]["ids"]; onm = om["dims"][0]["names"]; op = om["periods"]
    for a, n in zip(oa, onm): names.setdefault(a, n)
    for r in orecs:
        a = oa[r["k"][0]]
        for t, v in zip(r["t"], r["v"]): put(a, "LS_ILO", "_T", op[t], v)

# ---- OECD distributional national accounts: by income fifth -------------
# Household income broken down by quintile of the distribution, which lets the
# labor share be computed inside each fifth rather than for the country as a
# whole. Primary income is the denominator: compensation of employees, plus
# operating surplus and mixed income, plus property income received less paid.
# Pensions and other transfers are not in it, which is why the poorest fifth can
# still show a high labor share -- it is a share of what that group earns, not of
# what it lives on.
E = collections.defaultdict(dict)
ef = ROOT/"data/raw/egdna_inc.csv"
if ef.exists():
    for r in csv.DictReader(open(ef)):
        if not r["OBS_VALUE"] or r["UNIT_MEASURE"] != "XDC": continue
        E[(r["REF_AREA"], r["TIME_PERIOD"], r["INCOME_GROUP"])][
            (r["TRANSACTION"], r["ACCOUNTING_ENTRY"])] = float(r["OBS_VALUE"])
        names.setdefault(r["REF_AREA"], r["Reference area"])
    for (a, y, grp), d in E.items():
        if grp not in ("_T", "QG1", "QG2", "QG3", "QG4", "QG5"): continue
        b5 = d.get(("B5G", "B"))
        if not b5 or b5 <= 0: continue
        d1 = d.get(("D1", "C")); b3 = d.get(("B3G", "B"))
        dr = d.get(("D4", "C")); dp = d.get(("D4", "D"))
        if d1 is not None: put(a, "LS_Q_EMP", grp, y, d1/b5*100)
        if d1 is not None and b3 is not None: put(a, "LS_Q_ALL", grp, y, (d1+b3)/b5*100)
        if dr is not None and dp is not None: put(a, "PROP_Q", grp, y, (dr-dp)/b5*100)

# ---- WID: labor share within percentile groups, United States ----------
# data/raw/wid_slices.csv is the percentile-group subset of WID's per-country bulk
# files, extracted once so the build does not depend on re-downloading them.
W = collections.defaultdict(dict)
f = ROOT/"data/raw/wid_slices.csv"
if f.exists():
    for r in csv.DictReader(open(f)):
        if r["variable"] in ("sptlinj992", "sptkinj992", "sptincj992"):
            W[(r["area"], r["year"], r["percentile"])][r["variable"]] = float(r["value"])
    # Only countries with the labor/capital decomposition belong here; the plain
    # income shares for the other 44 live in the inequality dataset instead.
    wid_areas = sorted({a for (a, _, _), d in W.items() if "sptlinj992" in d})
    for a in wid_areas:
        yrs = sorted({y for aa, y, _ in W if aa == a}, key=int)
        for y in yrs:
            g = lambda p, v: W.get((a, y, p), {}).get(v)
            b, t = g("p0p90", "sptlinj992"), g("p90p100", "sptlinj992")
            alpha_l = b + t if (b is not None and t is not None) else None
            for code, p in (("P0P50", "p0p50"), ("P50P90", "p50p90"), ("P0P90", "p0p90"),
                            ("P90P100", "p90p100"), ("P99P100", "p99p100")):
                lin, inc = g(p, "sptlinj992"), g(p, "sptincj992")
                if lin is not None and inc: put(a, "LS_WID", code, y, lin/inc*100)
                if inc is not None: put(a, "INC_SHARE", code, y, inc*100)
            if alpha_l is not None:
                put(a, "LS_WID", "_T", y, alpha_l*100)
                put(a, "INC_SHARE", "_T", y, 100.0)
                l1, i1 = g("p99p100", "sptlinj992"), g("p99p100", "sptincj992")
                if l1 is not None and i1 is not None and (1-i1) > 0:
                    put(a, "LS_WID", "P0P99", y, (alpha_l-l1)/(1-i1)*100)
                    put(a, "INC_SHARE", "P0P99", y, (1-i1)*100)

# ---- assemble ----------------------------------------------------------
areas = sorted({a for a, _, _ in rec})
periods = sorted({y for s in rec.values() for y in s}, key=int)
ai = {a: i for i, a in enumerate(areas)}
mi = {m[0]: i for i, m in enumerate(MEASURES)}
gi = {g[0]: i for i, g in enumerate(GROUPS)}
ui = {u[0]: i for i, u in enumerate(UNITS)}
mu = {m[0]: m[2] for m in MEASURES}
pi = {y: i for i, y in enumerate(periods)}

payload = []
for (a, m, g), s in rec.items():
    ys = sorted(s, key=int)
    payload.append({"k": [ai[a], mi[m], gi[g], ui[mu[m]]],
                    "t": [pi[y] for y in ys], "v": [round(s[y], 4) for y in ys]})

meta = {
    "slug": SLUG, "id": "DF_LABOR_SHARE", "agency": "OECD / ILO / WID", "version": "2.0",
    "name": "Labor share of income",
    "description": "",
    "desc_html": (
      "The share of what a country produces that goes to labor rather than to profit "
      "and rent. The headline version of this number is wrong in two directions, and "
      "both corrections are separate dials here so you can see which one does the "
      "work.<br>"
      "<b>Employees only, or all workers.</b> The raw figure counts compensation of "
      "employees, meaning people on a payroll. A self-employed builder's earnings are "
      "not in it: the accounts file those under mixed income, alongside profit. So the "
      "raw number is not labor's share, it is employees' share, and it understates labor "
      "wherever many people work for themselves -- in Greece nearly a third of all hours "
      "worked. The <i>all workers</i> measures put them back by crediting the "
      "self-employed with what an employee earns per hour.<br>"
      "<b>GDP, or factor income.</b> Taxes on production sit inside GDP. A country "
      "levying 25 per cent VAT records a larger GDP for the same underlying production, "
      "so its labor share is mechanically smaller. Factor income -- what labor and "
      "capital actually receive -- removes that wedge. Against GDP, Sweden's labor share "
      "is five points below the United States. Against factor income it is four points "
      "above. Nothing about either economy changed, only the denominator.<br>"
      "<b>Where in the distribution.</b> Labor share falls as income rises, everywhere it "
      "can be measured. Choose an income fifth to see it inside one slice of the "
      "distribution: the poorest fifth of Canadians take 97 per cent of their income as "
      "labor, the richest fifth 77 per cent. For the United States the split is available "
      "by percentile back to 1913, and it is sharper still -- the bottom half take "
      "essentially all their income as labor, the top one per cent under half. Aggregate "
      "labor share and inequality are not separate subjects.<br>"
      "Sources: OECD Annual National Accounts, OECD Distributional National Accounts, the "
      "ILO SDG indicator series, and the "
      "<a href=\"https://wid.world/\" target=\"_blank\" rel=\"noopener noreferrer\">World "
      "Inequality Database</a>."),
    "desc_text": "Labor share of income on several denominators, with and without an "
      "adjustment for self-employment, plus the labor share within income groups for the "
      "United States back to 1913.",
    "topic": "SOC.SOC_INE",
    "dims": [
        {"id": "REF_AREA", "name": "Country", "ids": areas,
         "names": [names.get(a, a) for a in areas]},
        {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in MEASURES],
         "names": [m[1] for m in MEASURES], "default": 0},
        {"id": "INCOME_GROUP", "name": "Income group", "ids": [g[0] for g in GROUPS],
         "names": [g[1] for g in GROUPS], "default": 0},
        {"id": "UNIT_MEASURE", "name": "Measured as", "ids": [u[0] for u in UNITS],
         "names": [u[1] for u in UNITS]},
    ],
    "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
    "area_dim": "REF_AREA", "layout": "single",
    "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
    "source_url": "https://data-explorer.oecd.org/vis?fs[0]=Topic%2C0%7CEconomy%23ECO%23",
    "hidden_dims": {},
    "source_notes": [
      "Factor income is compensation of employees plus gross operating surplus and mixed "
      "income: the income side of the accounts, before taxes on production. It removes "
      "the VAT and excise wedge, which runs from near zero to over a fifth of GDP across "
      "these countries and otherwise drives much of the apparent cross-country spread. "
      "Labor share and capital share of factor income sum to exactly 100 per cent. GDP "
      "less production taxes would differ from it by the statistical discrepancy, which "
      "exceeds one per cent of GDP in about one country-year in ten.",
      "The self-employment adjustment multiplies compensation of employees by total "
      "labor input over employee labor input, which imputes to the self-employed the "
      "same earnings per hour, or per person, as employees. It is an assumption, not a "
      "measurement, and it is an upper bound wherever the self-employed earn less than "
      "employees.",
      "The income-fifth measures come from OECD's distributional national accounts, "
      "which allocate household income to quintiles of the distribution. The denominator "
      "is primary income: what the group earns, before pensions and other transfers. "
      "That is why the poorest fifth can show a high labor share -- it is a share of what "
      "they earn, not of what they live on. Quintiles are coarse: the fall in labor share "
      "is concentrated in the top few per cent, so the richest fifth understates it.",
      "The percentile split is WID's decomposition of pre-tax national income into "
      "labor and capital components within each percentile group, which WID publishes "
      "for the United States alone. Its denominator is pre-tax national income, not GDP, "
      "so its level is not comparable with the national accounts measures above.",
      "Labor share slightly above 100 per cent for the bottom half of the United States "
      "distribution is not an error. In those years that group's net capital income was "
      "negative -- interest paid on debt exceeded capital income received -- so labor "
      "income was larger than total income. It occurs around 1997 and 2007.",
    ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f'{len(payload)} series, {meta["n_obs"]:,} observations, {len(areas)} countries, '
      f'{periods[0]}-{periods[-1]}')
by = collections.Counter(m for _, m, _ in rec)
for m, n, _ in MEASURES:
    cs = len({a for a, mm, _ in rec if mm == m})
    print(f'  {m:16} {cs:>4} countries  {n[:56]}')
