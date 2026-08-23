#!/usr/bin/env python3
"""Material deprivation: what people actually cannot afford.

Income poverty is a position in a distribution. It says someone falls below 60
per cent of their country's median, which is a statement about the shape of the
distribution rather than about their life. Deprivation measures the other thing
directly: whether the home is warm, whether the bills are paid, whether an
unexpected bill can be met at all.

The two disagree often enough to be worth holding side by side, and the income
dial here is what makes that visible: every item can be read for people above the
poverty line as well as below it.
"""
import csv, gzip, json, pathlib, collections, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
RAW  = ROOT/"data/raw/estat"
SLUG = "ESTAT__DF_DEPRIVATION"
API  = ("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
        "{}?format=SDMX-CSV")

# code, table, display name, and the lev_diff values to add up (mdes09 only)
ITEMS = [
 ("UNEXPECTED",  "ilc_mdes04", "Cannot meet an unexpected expense", None),
 ("HOLIDAY",     "ilc_mdes02", "Cannot afford a week away from home", None),
 ("WARM",        "ilc_mdes01", "Cannot keep the home adequately warm", None),
 ("MEAL",        "ilc_mdes03", "Cannot afford a proper meal every second day", None),
 ("ENDS_MEET",   "ilc_mdes09", "Making ends meet with difficulty", ("DIF", "GRT")),
 ("ARREARS",     "ilc_mdes05", "Behind on rent, utilities or loan payments", None),
 ("ARREARS_RENT", "ilc_mdes06", "Behind on rent or mortgage", None),
 ("ARREARS_UTIL", "ilc_mdes07", "Behind on utility bills", None),
 ("ARREARS_LOAN", "ilc_mdes08", "Behind on loan or hire purchase payments", None),
 ("HOUSING_COST", "ilc_lvho07a", "Housing costs above 40 per cent of income", None),
 ("OVERCROWD",   "ilc_lvho05a", "Living in an overcrowded home", None),
 ("HOUSING_DEP", "ilc_mdho06a", "Severe housing deprivation", None),
 ("MSD",         "ilc_mdsd07", "Material and social deprivation rate", None),
 ("SMD",         "ilc_mddd11", "Severe material deprivation rate", None),
]
POS = [("TOTAL", "Everyone"), ("B_60", "Below the poverty line"),
       ("A_60", "Above the poverty line")]

I2 = {'AT':'AUT','BE':'BEL','BG':'BGR','CY':'CYP','CZ':'CZE','DE':'DEU','DK':'DNK',
 'EE':'EST','EL':'GRC','ES':'ESP','FI':'FIN','FR':'FRA','HR':'HRV','HU':'HUN',
 'IE':'IRL','IT':'ITA','LT':'LTU','LU':'LUX','LV':'LVA','MT':'MLT','NL':'NLD',
 'PL':'POL','PT':'PRT','RO':'ROU','SE':'SWE','SI':'SVN','SK':'SVK','UK':'GBR',
 'IS':'ISL','NO':'NOR','CH':'CHE','LI':'LIE','ME':'MNE','MK':'MKD','RS':'SRB',
 'TR':'TUR','AL':'ALB','BA':'BIH','XK':'XKV','MD':'MDA','UA':'UKR'}
KEEP_AGG = {"EU27_2020", "EU28", "EA19", "EA20", "EU27_2007"}
def area(g): return I2.get(g) or (g if g in KEEP_AGG else None)

def rows(tbl):
    p = RAW/f"{tbl}.csv"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        print(f"  fetching {tbl} ...")
        with urllib.request.urlopen(API.format(tbl), timeout=900) as r: p.write_bytes(r.read())
    return csv.DictReader(open(p))

rec = {}
for code, tbl, _, levs in ITEMS:
    n = 0
    acc = collections.defaultdict(float)
    for r in rows(tbl):
        if r.get("unit") != "PC" or not r["OBS_VALUE"]: continue
        a = area(r["geo"])
        if not a: continue
        # collapse every breakdown except income position to its published total
        if r.get("hhcomp", "TOTAL") != "TOTAL": continue
        if r.get("age", "TOTAL") != "TOTAL": continue
        if r.get("sex", "T") != "T": continue
        if levs is not None and r.get("lev_diff") not in levs: continue
        if levs is None and "lev_diff" in r: continue
        pos = r.get("rskpovth", "TOTAL")
        if pos not in ("TOTAL", "A_60", "B_60"): continue
        try: v = float(r["OBS_VALUE"])
        except ValueError: continue
        acc[(a, pos, r["TIME_PERIOD"])] += v
        n += 1
    for (a, pos, y), v in acc.items():
        rec.setdefault((a, code, pos), {})[y] = v
    print(f"  {code:14} {tbl:12} {n:>7,} rows -> {len(acc):>6,} points")

names = {}
for mf in sorted((SITE/"flows").glob("*/meta.json")):
    try: m = json.loads(mf.read_text())
    except Exception: continue
    for d in m.get("dims", []):
        if d.get("id") == "REF_AREA": names.update(dict(zip(d["ids"], d["names"])))

areas = sorted({a for a, _, _ in rec})
items = [i for i in ITEMS if any(k[1] == i[0] for k in rec)]
poss  = [p for p in POS if any(k[2] == p[0] for k in rec)]
periods = sorted({y for s in rec.values() for y in s}, key=int)
ai={a:i for i,a in enumerate(areas)}; mi={i[0]:n for n,i in enumerate(items)}
psi={p[0]:i for i,p in enumerate(poss)}; pi={y:i for i,y in enumerate(periods)}

payload=[]
for (a, c, pos), s in rec.items():
    ys = sorted(s, key=int)
    payload.append({"k": [ai[a], mi[c], psi[pos], 0],
                    "t": [pi[y] for y in ys], "v": [round(s[y], 4) for y in ys]})

meta = {
 "slug": SLUG, "id": "DF_DEPRIVATION", "agency": "Eurostat", "version": "1.0",
 "name": "Material deprivation", "description": "",
 "desc_html": (
   "Income poverty is a position in a distribution: it says someone falls below 60 per "
   "cent of their country's median, which describes the shape of the distribution rather "
   "than the life. Deprivation asks the question directly. Is the home warm. Are the "
   "bills paid. Could an unexpected expense be met at all.<br>"
   "The <b>Income position</b> dial is what makes this worth having next to the poverty "
   "rate. Every item can be read for people above the poverty line as well as below it, "
   "and the two measures disagree more than they agree. A country can hold its income "
   "poverty rate down and still have a large share of people who cannot heat their "
   "homes; a country with high measured poverty can have low deprivation because its "
   "median is high and living costs are low.<br>"
   "Where they diverge is usually about prices and about what the state supplies free. "
   "Deprivation catches the cost of housing and energy, which a relative income line "
   "cannot see at all.<br>"
   "Source: Eurostat, EU Statistics on Income and Living Conditions (EU-SILC)."),
 "desc_text": "What people cannot afford -- heating, a proper meal, an unexpected "
   "expense, rent and utility bills -- readable separately for people above and below "
   "the income poverty line.",
 "topic": "SOC.SOC_INE",
 "dims": [
   {"id": "REF_AREA", "name": "Country", "ids": areas,
    "names": [names.get(a, a) for a in areas]},
   {"id": "ITEM", "name": "Cannot afford", "ids": [i[0] for i in items],
    "names": [i[2] for i in items], "default": 0},
   {"id": "INCOME_POS", "name": "Income position", "ids": [p[0] for p in poss],
    "names": [p[1] for p in poss], "default": 0},
   {"id": "UNIT_MEASURE", "name": "Measured as", "ids": ["PT_POP"],
    "names": ["Percentage of people"]},
 ],
 "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
 "area_dim": "REF_AREA", "layout": "single",
 "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
 "source_url": "https://ec.europa.eu/eurostat/databrowser/view/ilc_mdes04/default/table",
 "hidden_dims": {},
 "source_notes": [
   "Not an OECD table. Eurostat, EU-SILC. Every item is the share of people in "
   "households reporting that they cannot afford the thing, or are behind on the "
   "payment. They are self-reported, which is the point: affordability is being "
   "measured, not consumption. A household that chooses not to take a holiday is not "
   "counted; one that cannot is.",
   "Below and above the poverty line mean below and above 60 per cent of national "
   "median equivalised disposable income, the same threshold used in the poverty and "
   "in-work poverty tables on this site.",
   "'Making ends meet with difficulty' adds Eurostat's two hardest categories, with "
   "difficulty and with great difficulty; the four easier categories are excluded.",
   "The material and social deprivation rate counts people lacking at least five of "
   "thirteen items, and runs from 2014. The severe material deprivation rate is the "
   "older measure, on a nine-item list, and Eurostat discontinued it after 2020. They "
   "are kept as separate indicators rather than spliced, because the item lists differ "
   "and the levels are not comparable. Both are published only for the population as a "
   "whole, not split by income position.",
 ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(payload, separators=(",",":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",",":")))
print(f'\n{len(payload)} series, {meta["n_obs"]:,} observations, {len(areas)} areas, '
      f'{periods[0]}-{periods[-1]}')
