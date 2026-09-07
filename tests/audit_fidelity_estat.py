#!/usr/bin/env python3
"""Re-download the Eurostat tables and compare them to what we serve.

The OECD fidelity audit covers 51 datasets. These two are built from nine and
fourteen Eurostat tables respectively, folded into one dimension each, so the
folding is exactly where a mistake would hide: a category mapped to the wrong
code produces plausible numbers under the wrong label.
"""
import csv, gzip, io, json, pathlib, urllib.request, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
API = ("https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/"
       "{}?format=SDMX-CSV")
I2 = {'AT':'AUT','BE':'BEL','BG':'BGR','CY':'CYP','CZ':'CZE','DE':'DEU','DK':'DNK',
 'EE':'EST','EL':'GRC','ES':'ESP','FI':'FIN','FR':'FRA','HR':'HRV','HU':'HUN',
 'IE':'IRL','IT':'ITA','LT':'LTU','LU':'LUX','LV':'LVA','MT':'MLT','NL':'NLD',
 'PL':'POL','PT':'PRT','RO':'ROU','SE':'SWE','SI':'SVN','SK':'SVK','UK':'GBR',
 'IS':'ISL','NO':'NOR','CH':'CHE','LI':'LIE','ME':'MNE','MK':'MKD','RS':'SRB',
 'TR':'TUR','AL':'ALB','BA':'BIH','XK':'XKV','MD':'MDA','UA':'UKR'}
KEEP_AGG = {"EU27_2020","EU28","EA19","EA20","EU27_2007"}
def area(g): return I2.get(g) or (g if g in KEEP_AGG else None)

def load(slug):
    d = ROOT/"site/data/flows"/slug
    m = json.loads((d/"meta.json").read_text())
    r = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
    return m, r

def fetch(table):
    with urllib.request.urlopen(API.format(table), timeout=1200) as r:
        return r.read().decode("utf-8", "replace")

# slug -> the mapping from a source row to the site's breakdown code
def inwork_code(r):
    t = r["DATAFLOW"].split(":")[1].split("(")[0].lower()
    if t == "ilc_iw01": return {"EMP":"EMP","SAL":"SAL","NSAL":"NSAL"}.get(r.get("wstatus"))
    if t == "ilc_iw05": return {"SAL_PERM":"SAL_PERM","SAL_TEMP":"SAL_TEMP"}.get(r.get("wstatus"))
    if t == "ilc_iw07": return {"FT":"FT","PT":"PT"}.get(r.get("worktime"))
    if t == "ilc_iw06": return {"Y1":"DUR_FULL","Y_LT1":"DUR_PART"}.get(r.get("duration"))
    if t == "ilc_iw04": return {"ED0-2":"ED_LOW","ED3_4":"ED_MID","ED5-8":"ED_HIGH"}.get(r.get("isced11"))
    if t == "ilc_iw03":
        if r.get("hhcomp") != "TOTAL": return None
        return {"WI0-02":"WI_VLOW","WI02-045":"WI_LOW","WI045-055":"WI_MID",
                "WI055-085":"WI_HIGH","WI085-1":"WI_VHIGH"}.get(r.get("workint"))
    if t == "ilc_iw02":
        return {"A1":"HH_ALONE","A1_DCH":"HH_LONE_CH","A_GE2_DCH":"HH_2A_CH",
                "A_GE2_NDCH":"HH_2A_NCH","DCH":"HH_CH","NDCH":"HH_NCH"}.get(r.get("hhcomp"))
    if t == "ilc_iw15":
        return {"NAT":"CIT_NAT","EU27_2020_FOR":"CIT_EU","NEU27_2020_FOR":"CIT_NONEU"}.get(r.get("citizen"))
    if t == "ilc_iw16":
        return {"NAT":"BORN_NAT","EU27_2020_FOR":"BORN_EU","NEU27_2020_FOR":"BORN_NONEU"}.get(r.get("c_birth"))
    return None

AGE_IN = {"Y_GE18":"_T","Y18-24":"Y18-24","Y25-54":"Y25-54","Y55-64":"Y55-64",
          "Y_GE65":"Y_GE65","Y18-64":"Y18-64"}

m, recs = load("ESTAT__DF_INWORK_POV")
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
ours = {}
for r in recs:
    k = (D["REF_AREA"]["ids"][r["k"][ids.index("REF_AREA")]],
         D["BREAKDOWN"]["ids"][r["k"][ids.index("BREAKDOWN")]],
         D["SEX"]["ids"][r["k"][ids.index("SEX")]],
         D["AGE"]["ids"][r["k"][ids.index("AGE")]])
    for t, v in zip(r["t"], r["v"]): ours[(k, P[t])] = v

tables = ["ilc_iw01","ilc_iw02","ilc_iw03","ilc_iw04","ilc_iw05",
          "ilc_iw06","ilc_iw07","ilc_iw15","ilc_iw16"]
matched = mism = missing = 0
ex = []
for t in tables:
    try: rows = list(csv.DictReader(io.StringIO(fetch(t))))
    except Exception as e:
        print(f"  {t}: fetch failed {type(e).__name__}"); continue
    n_t = n_m = 0
    for r in rows:
        if r.get("unit") != "PC" or not r.get("OBS_VALUE"): continue
        a = area(r["geo"]);  code = inwork_code(r)
        if not a or not code: continue
        # ilc_iw03 carries no age column and is published for 18-64, which is how
        # it is stored. Everything else without an age column is 18 and over.
        tbl = r["DATAFLOW"].split(":")[1].split("(")[0].lower()
        if "age" in r and r["age"]:
            age = AGE_IN.get(r["age"])
        else:
            age = "Y18-64" if tbl == "ilc_iw03" else "_T"
        if age is None: continue
        sex = r.get("sex", "T")
        got = ours.get(((a, code, sex, age), r["TIME_PERIOD"]))
        if got is None: missing += 1; continue
        try: src = float(r["OBS_VALUE"])
        except ValueError: continue
        n_t += 1
        if abs(got - src) > 1e-6:
            n_m += 1
            if len(ex) < 4: ex.append((t, a, code, r["TIME_PERIOD"], src, got))
    matched += n_t - n_m; mism += n_m
    print(f"  {t}: compared {n_t:>6,}  mismatched {n_m}")
print(f"\nin-work poverty: matched {matched:,}  mismatched {mism}  "
      f"source rows with no site cell {missing:,}")
for e in ex: print("   ", e)

# ---- material deprivation: fourteen tables folded into one "Cannot afford" dial
ITEMS = {"ilc_mdes04":"UNEXPECTED","ilc_mdes02":"HOLIDAY","ilc_mdes01":"WARM",
 "ilc_mdes03":"MEAL","ilc_mdes05":"ARREARS","ilc_mdes06":"ARREARS_RENT",
 "ilc_mdes07":"ARREARS_UTIL","ilc_mdes08":"ARREARS_LOAN","ilc_lvho07a":"HOUSING_COST",
 "ilc_lvho05a":"OVERCROWD","ilc_mdho06a":"HOUSING_DEP","ilc_mdsd07":"MSD",
 "ilc_mddd11":"SMD"}
ENDS = {"ilc_mdes09":"ENDS_MEET"}      # summed from two hardest categories

m2, r2 = load("ESTAT__DF_DEPRIVATION")
i2 = [x["id"] for x in m2["dims"]]; D2 = {x["id"]: x for x in m2["dims"]}; P2 = m2["periods"]
ours2 = {}
for r in r2:
    k = (D2["REF_AREA"]["ids"][r["k"][i2.index("REF_AREA")]],
         D2["ITEM"]["ids"][r["k"][i2.index("ITEM")]],
         D2["INCOME_POS"]["ids"][r["k"][i2.index("INCOME_POS")]])
    for t, v in zip(r["t"], r["v"]): ours2[(k, P2[t])] = v

print()
tot_m = tot_x = 0
for tbl, code in list(ITEMS.items()) + list(ENDS.items()):
    try: rows = list(csv.DictReader(io.StringIO(fetch(tbl))))
    except Exception as e:
        print(f"  {tbl}: fetch failed {type(e).__name__}"); continue
    acc = collections.defaultdict(float); seen = set()
    for r in rows:
        if r.get("unit") != "PC" or not r.get("OBS_VALUE"): continue
        a = area(r["geo"])
        if not a: continue
        if r.get("hhcomp", "TOTAL") != "TOTAL": continue
        if r.get("age", "TOTAL") != "TOTAL": continue
        if r.get("sex", "T") != "T": continue
        pos = r.get("rskpovth", "TOTAL")
        if pos not in ("TOTAL", "A_60", "B_60"): continue
        if tbl in ENDS:
            if r.get("lev_diff") not in ("DIF", "GRT"): continue
        elif "lev_diff" in r: continue
        try: v = float(r["OBS_VALUE"])
        except ValueError: continue
        acc[(a, pos, r["TIME_PERIOD"])] += v; seen.add((a, pos, r["TIME_PERIOD"]))
    n_t = n_m = 0
    for (a, pos, per), v in acc.items():
        got = ours2.get(((a, code, pos), per))
        if got is None: continue
        n_t += 1
        if abs(got - v) > 1e-4: n_m += 1
    tot_m += n_t - n_m; tot_x += n_m
    print(f"  {tbl}: compared {n_t:>6,}  mismatched {n_m}")
print(f"\nmaterial deprivation: matched {tot_m:,}  mismatched {tot_x}")
