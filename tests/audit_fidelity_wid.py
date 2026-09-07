#!/usr/bin/env python3
"""Re-download WID's own country files and compare the measures taken from them.

Three things on the site come straight from WID's bulk distribution rather than
through Our World in Data: the female share of labor income, the income shares
of the bottom half, middle 40 and top tenth, and the labor-capital split behind
the labor share dataset. They were extracted once into data/raw/wid_slices.csv,
so the extract itself is what needs checking against WID.
"""
import csv, gzip, io, json, os, pathlib, urllib.request, zipfile, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
CACHE = pathlib.Path("/private/tmp/claude-501/-Users-alexhoffman-Documents/"
                     "5b734f3a-e90a-44b8-ab72-abd591c4d0c9/scratchpad/widcheck")
CACHE.mkdir(parents=True, exist_ok=True)
I3 = {'AU':'AUS','AT':'AUT','BE':'BEL','CA':'CAN','CL':'CHL','CO':'COL','CR':'CRI',
'CZ':'CZE','DK':'DNK','EE':'EST','FI':'FIN','FR':'FRA','DE':'DEU','GR':'GRC','HU':'HUN',
'IS':'ISL','IE':'IRL','IL':'ISR','IT':'ITA','JP':'JPN','KR':'KOR','LV':'LVA','LT':'LTU',
'LU':'LUX','MX':'MEX','NL':'NLD','NZ':'NZL','NO':'NOR','PL':'POL','PT':'PRT','SK':'SVK',
'SI':'SVN','ES':'ESP','SE':'SWE','CH':'CHE','TR':'TUR','GB':'GBR','US':'USA'}
WANT = {"spllinf992", "sptincj992", "sptlinj992", "sptkinj992"}
PCT = {"p0p50","p50p90","p0p90","p90p100","p99p100","p0p100","p0p99"}

def country_rows(i2):
    """WID publishes one zip per country; cache them so a re-run is cheap."""
    out = CACHE/f"{i2}.csv"
    if not out.exists():
        url = f"https://wid.world/bulk_download/WID_fulldataset_{i2}.zip"
        try:
            with urllib.request.urlopen(url, timeout=900) as r: blob = r.read()
        except Exception: out.write_text(""); return []
        rows = []
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            name = next((n for n in z.namelist() if n.endswith(f"WID_data_{i2}.csv")), None)
            if name:
                for line in z.read(name).decode("utf-8", "replace").splitlines()[1:]:
                    p = line.split(";")
                    if len(p) > 4 and p[1] in WANT and p[2] in PCT and p[4]:
                        rows.append((p[1], p[2], p[3], p[4]))
        with open(out, "w", newline="") as f:
            csv.writer(f).writerows(rows)
    with open(out) as f:
        return list(csv.reader(f))

# what the site serves
def load(slug):
    d = ROOT/"site/data/flows"/slug
    m = json.loads((d/"meta.json").read_text())
    return m, json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))

m, recs = load("WID_LIS__DF_CONCENTRATION")
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
ai, mi = ids.index("REF_AREA"), ids.index("MEASURE")
site = {}
for r in recs:
    k = (D["REF_AREA"]["ids"][r["k"][ai]], D["MEASURE"]["ids"][r["k"][mi]])
    for t, v in zip(r["t"], r["v"]): site[(k, P[t])] = v
areas = set(D["REF_AREA"]["ids"])

MAP = {("spllinf992","p0p100"):"FEM_LABINC", ("sptincj992","p0p50"):"INC_P0P50",
       ("sptincj992","p50p90"):"INC_P50P90", ("sptincj992","p90p100"):"INC_P90P100"}
n = x = 0; ex = []; fetched = 0
for i2, i3 in sorted(I3.items()):
    if i3 not in areas: continue
    rows = country_rows(i2)
    if rows: fetched += 1
    for var, pct, year, val in rows:
        code = MAP.get((var, pct))
        if not code: continue
        got = site.get(((i3, code), year))
        if got is None: continue
        try: v = float(val)*100
        except ValueError: continue
        n += 1
        if abs(got - v) > 1e-4:
            x += 1
            if len(ex) < 4: ex.append((i3, code, year, round(v,4), got))
print(f"WID country files re-downloaded: {fetched}")
print(f"inequality measures from WID: compared {n:,}  mismatched {x}")
for e in ex: print("   ", e)

# the labor/capital split behind the labor share dataset (United States)
m2, r2 = load("OWID__LABOR_SHARE")
i2l = [x["id"] for x in m2["dims"]]; D2 = {x["id"]: x for x in m2["dims"]}; P2 = m2["periods"]
ls = {}
for r in r2:
    k = (D2["REF_AREA"]["ids"][r["k"][i2l.index("REF_AREA")]],
         D2["MEASURE"]["ids"][r["k"][i2l.index("MEASURE")]],
         D2["INCOME_GROUP"]["ids"][r["k"][i2l.index("INCOME_GROUP")]])
    for t, v in zip(r["t"], r["v"]): ls[(k, P2[t])] = v
rows = country_rows("US")
byyear = collections.defaultdict(dict)
for var, pct, year, val in rows:
    try: byyear[(year, pct)][var] = float(val)
    except ValueError: pass
GRP = {"p0p50":"P0P50","p50p90":"P50P90","p0p90":"P0P90",
       "p90p100":"P90P100","p99p100":"P99P100"}
n2 = x2 = 0; ex2 = []
for (year, pct), d in byyear.items():
    g = GRP.get(pct)
    if not g: continue
    lin, inc = d.get("sptlinj992"), d.get("sptincj992")
    if lin is None or not inc: continue
    exp = lin/inc*100
    got = ls.get((("USA", "LS", g), year))
    if got is None: continue
    n2 += 1
    if abs(got - exp) > 1e-3:
        x2 += 1
        if len(ex2) < 3: ex2.append((g, year, round(exp,4), got))
print(f"US labor share within percentile groups: recomputed {n2:,}  disagreeing {x2}")
for e in ex2: print("   ", e)
