#!/usr/bin/env python3
"""In-work poverty, from the nine Eurostat EU-SILC tables that measure it.

Poverty statistics usually describe people who are out of work. This measures the
people the labour market is supposed to have taken care of: those in work, living
below 60 per cent of their country's median income anyway. It is the single number
that tests whether having a job is sufficient.

Eurostat cuts it nine ways -- by contract, by hours, by education, by how much the
household works, by how much of the year was worked, by citizenship, by birthplace,
by household composition, and by age and sex. Those cuts are folded into one
"Who" dimension here so they can be compared against each other directly.
"""
import csv, gzip, json, pathlib, collections, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
RAW  = ROOT/"data/raw/estat"
SLUG = "ESTAT__DF_INWORK_POV"
API  = ("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
        "{}?format=SDMX-CSV")

TABLES = ["ilc_iw01", "ilc_iw02", "ilc_iw03", "ilc_iw04", "ilc_iw05",
          "ilc_iw06", "ilc_iw07", "ilc_iw15", "ilc_iw16"]

# breakdown code -> display name, in the order they should read
BREAKDOWN = [
    ("EMP",       "Everyone in work"),
    ("SAL",       "Employees"),
    ("NSAL",      "Self-employed"),
    ("SAL_PERM",  "Employees on permanent contracts"),
    ("SAL_TEMP",  "Employees on temporary contracts"),
    ("FT",        "Working full-time"),
    ("PT",        "Working part-time"),
    ("DUR_FULL",  "Worked the whole year"),
    ("DUR_PART",  "Worked less than the whole year"),
    ("ED_LOW",    "Left school at lower secondary or earlier"),
    ("ED_MID",    "Upper secondary or post-secondary"),
    ("ED_HIGH",   "Tertiary educated"),
    ("WI_VLOW",   "Household works almost none of its capacity"),
    ("WI_LOW",    "Household works a fifth to a half of its capacity"),
    ("WI_MID",    "Household works about half its capacity"),
    ("WI_HIGH",   "Household works most of its capacity"),
    ("WI_VHIGH",  "Household works nearly all its capacity"),
    ("HH_ALONE",  "Living alone"),
    ("HH_LONE_CH", "Lone parent with children"),
    ("HH_2A_CH",  "Two or more adults with children"),
    ("HH_2A_NCH", "Two or more adults, no children"),
    ("HH_CH",     "Households with children"),
    ("HH_NCH",    "Households without children"),
    ("CIT_NAT",   "Citizens of the country"),
    ("CIT_EU",    "Citizens of another EU country"),
    ("CIT_NONEU", "Citizens of a non-EU country"),
    ("BORN_NAT",  "Born in the country"),
    ("BORN_EU",   "Born in another EU country"),
    ("BORN_NONEU", "Born outside the EU"),
]
AGES = [("_T", "18 and over"), ("Y18-24", "18 to 24"), ("Y25-54", "25 to 54"),
        ("Y55-64", "55 to 64"), ("Y_GE65", "65 and over"), ("Y18-64", "18 to 64")]
SEXES = [("T", "Total"), ("F", "Women"), ("M", "Men")]

AGE_IN = {"Y_GE18": "_T", "Y18-24": "Y18-24", "Y25-54": "Y25-54",
          "Y55-64": "Y55-64", "Y_GE65": "Y_GE65", "Y18-64": "Y18-64"}

# Eurostat geo -> the area codes the rest of the site already uses
I2 = {'AT':'AUT','BE':'BEL','BG':'BGR','CY':'CYP','CZ':'CZE','DE':'DEU','DK':'DNK',
 'EE':'EST','EL':'GRC','ES':'ESP','FI':'FIN','FR':'FRA','HR':'HRV','HU':'HUN',
 'IE':'IRL','IT':'ITA','LT':'LTU','LU':'LUX','LV':'LVA','MT':'MLT','NL':'NLD',
 'PL':'POL','PT':'PRT','RO':'ROU','SE':'SWE','SI':'SVN','SK':'SVK','UK':'GBR',
 'IS':'ISL','NO':'NOR','CH':'CHE','LI':'LIE','ME':'MNE','MK':'MKD','RS':'SRB',
 'TR':'TUR','AL':'ALB','BA':'BIH','XK':'XKV','MD':'MDA','UA':'UKR'}
KEEP_AGG = {"EU27_2020", "EU28", "EA19", "EA20", "EU27_2007"}

rec = {}
def put(a, b, s, g, y, v):
    if v is None: return
    rec.setdefault((a, b, s, g), {})[y] = v

def area(g):
    if g in I2: return I2[g]
    return g if g in KEEP_AGG else None

def rows(tbl):
    p = RAW/f"{tbl}.csv"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        print(f"  fetching {tbl} ...")
        with urllib.request.urlopen(API.format(tbl), timeout=900) as r:
            p.write_bytes(r.read())
    for r in csv.DictReader(open(p)):
        if r.get("unit") != "PC" or not r["OBS_VALUE"]: continue
        a = area(r["geo"])
        if not a: continue
        try: v = float(r["OBS_VALUE"])
        except ValueError: continue
        yield r, a, v

# ilc_iw01 -- everyone in work, employees, self-employed, by age and sex
for r, a, v in rows("ilc_iw01"):
    if r["wstatus"] not in ("EMP", "SAL", "NSAL"): continue
    ag = AGE_IN.get(r["age"])
    if not ag: continue
    put(a, r["wstatus"], r["sex"], ag, r["TIME_PERIOD"], v)

# ilc_iw05 -- permanent vs temporary contract, by sex
for r, a, v in rows("ilc_iw05"):
    if r["wstatus"] not in ("SAL_PERM", "SAL_TEMP"): continue
    put(a, r["wstatus"], r["sex"], "_T", r["TIME_PERIOD"], v)

# ilc_iw07 -- full-time vs part-time
for r, a, v in rows("ilc_iw07"):
    m = {"FT": "FT", "PT": "PT"}.get(r["worktime"])
    if m: put(a, m, "T", "_T", r["TIME_PERIOD"], v)

# ilc_iw06 -- worked the whole year or not
for r, a, v in rows("ilc_iw06"):
    m = {"Y1": "DUR_FULL", "Y_LT1": "DUR_PART"}.get(r["duration"])
    if m: put(a, m, "T", "_T", r["TIME_PERIOD"], v)

# ilc_iw04 -- education
for r, a, v in rows("ilc_iw04"):
    m = {"ED0-2": "ED_LOW", "ED3_4": "ED_MID", "ED5-8": "ED_HIGH"}.get(r["isced11"])
    if m: put(a, m, "T", "_T", r["TIME_PERIOD"], v)

# ilc_iw03 -- household work intensity, 18-64 only. The overlapping summary bands
# (WI0-05, WI02-1) are dropped so the categories partition the range.
WI = {"WI0-02": "WI_VLOW", "WI02-045": "WI_LOW", "WI045-055": "WI_MID",
      "WI055-085": "WI_HIGH", "WI085-1": "WI_VHIGH"}
for r, a, v in rows("ilc_iw03"):
    if r["hhcomp"] != "TOTAL": continue
    m = WI.get(r["workint"])
    if m: put(a, m, "T", "Y18-64", r["TIME_PERIOD"], v)

# ilc_iw02 -- household composition
HH = {"A1": "HH_ALONE", "A1_DCH": "HH_LONE_CH", "A_GE2_DCH": "HH_2A_CH",
      "A_GE2_NDCH": "HH_2A_NCH", "DCH": "HH_CH", "NDCH": "HH_NCH"}
for r, a, v in rows("ilc_iw02"):
    m = HH.get(r["hhcomp"])
    if m: put(a, m, "T", "_T", r["TIME_PERIOD"], v)

# ilc_iw15 / ilc_iw16 -- citizenship and country of birth. Only the current EU27
# vintage is used; the 2007 and EU28 vintages restate the same people.
for tbl, col, pre in (("ilc_iw15", "citizen", "CIT"), ("ilc_iw16", "c_birth", "BORN")):
    M = {"NAT": f"{pre}_NAT", "EU27_2020_FOR": f"{pre}_EU",
         "NEU27_2020_FOR": f"{pre}_NONEU"}
    for r, a, v in rows(tbl):
        m = M.get(r[col])
        if not m: continue
        ag = AGE_IN.get(r["age"])
        if not ag: continue
        put(a, m, r["sex"], ag, r["TIME_PERIOD"], v)

# ---- assemble ----------------------------------------------------------
names = {}
for mf in sorted((SITE/"flows").glob("*/meta.json")):
    try: m = json.loads(mf.read_text())
    except Exception: continue
    for d in m.get("dims", []):
        if d.get("id") == "REF_AREA": names.update(dict(zip(d["ids"], d["names"])))

areas   = sorted({a for a, _, _, _ in rec})
bd      = [b for b in BREAKDOWN if any(k[1] == b[0] for k in rec)]
sexes   = [s for s in SEXES if any(k[2] == s[0] for k in rec)]
ages    = [g for g in AGES if any(k[3] == g[0] for k in rec)]
periods = sorted({y for s in rec.values() for y in s}, key=int)
ai = {a: i for i, a in enumerate(areas)}; bi = {b[0]: i for i, b in enumerate(bd)}
si = {s[0]: i for i, s in enumerate(sexes)}; gi = {g[0]: i for i, g in enumerate(ages)}
pi = {y: i for i, y in enumerate(periods)}

payload = []
for (a, b, s, g), ser in rec.items():
    ys = sorted(ser, key=int)
    payload.append({"k": [ai[a], bi[b], si[s], gi[g], 0],
                    "t": [pi[y] for y in ys], "v": [round(ser[y], 4) for y in ys]})

meta = {
  "slug": SLUG, "id": "DF_INWORK_POV", "agency": "Eurostat", "version": "1.0",
  "name": "In-work poverty", "description": "",
  "desc_html": (
    "The share of people who work and are poor anyway: in work, yet living in a "
    "household below 60 per cent of their country's median income. Poverty figures "
    "usually describe people outside the labor market. This one describes the people "
    "it was supposed to have taken care of, and it is the number that tests whether "
    "having a job is enough.<br>"
    "The <b>Who</b> dial cuts it nine ways, and the cuts are the argument. Temporary "
    "contracts against permanent ones. Part-time against full-time. A full year worked "
    "against a partial one. How hard the whole household works, which separates low pay "
    "from too few hours. Education, citizenship, birthplace, and who else is at home.<br>"
    "A high rate among people on permanent full-time contracts means wages are too low. "
    "A high rate concentrated among the temporary and the part-time means the problem is "
    "access to hours rather than the hourly rate. The two call for different remedies, "
    "and the dial separates them.<br>"
    "Source: Eurostat, EU Statistics on Income and Living Conditions (EU-SILC), tables "
    "ilc_iw01 to ilc_iw16."),
  "desc_text": "Share of people who are in work and still living below 60 per cent of "
    "median income, cut by contract type, hours, household work intensity, education, "
    "citizenship, birthplace and household composition.",
  "topic": "SOC.SOC_INE",
  "dims": [
    {"id": "REF_AREA", "name": "Country", "ids": areas,
     "names": [names.get(a, a) for a in areas]},
    {"id": "BREAKDOWN", "name": "Who", "ids": [b[0] for b in bd],
     "names": [b[1] for b in bd], "default": 0},
    {"id": "SEX", "name": "Sex", "ids": [s[0] for s in sexes],
     "names": [s[1] for s in sexes], "default": 0},
    {"id": "AGE", "name": "Age", "ids": [g[0] for g in ages],
     "names": [g[1] for g in ages], "default": 0},
    {"id": "UNIT_MEASURE", "name": "Measured as", "ids": ["PT_POP"],
     "names": ["Percentage of people in work"]},
  ],
  "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
  "area_dim": "REF_AREA", "layout": "single",
  "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
  "source_url": "https://ec.europa.eu/eurostat/databrowser/view/ilc_iw01/default/table",
  "hidden_dims": {},
  "source_notes": [
    "Not an OECD table. Eurostat, EU-SILC. The poverty line is 60 per cent of national "
    "median equivalised disposable income, so it moves with each country's own median: "
    "this measures distance from the national middle, not an absolute standard of living.",
    "The household work-intensity breakdown is published for ages 18 to 64; every other "
    "breakdown covers 18 and over. Work intensity is the share of the months the working-"
    "age adults in a household could have worked that they actually did work.",
    "The overlapping work-intensity summary bands Eurostat also publishes are excluded, "
    "so the five categories shown partition the range without double counting. For "
    "citizenship and country of birth only the current EU27 definition is used; the "
    "earlier EU27 and EU28 vintages restate the same people against different borders.",
  ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f'{len(payload)} series, {meta["n_obs"]:,} observations, {len(areas)} areas, '
      f'{periods[0]}-{periods[-1]}')
c = collections.Counter(k[1] for k in rec)
for code, nm in bd: print(f'  {code:12} {c[code]:>5} series  {nm[:56]}')
