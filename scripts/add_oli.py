#!/usr/bin/env python3
"""The Online Labour Index: where the world's online gig work is done.

Platform work is absent from national labour statistics. Nobody's labour force
survey counts the Kenyan who writes copy for a London agency through Upwork, and
no OECD table has a column for it. The Online Labour Index, built at the Oxford
Internet Institute, measures it by scraping the platforms themselves.

Two things are measured here. Where the workers are: the share of the world's
online freelancers who live in each country, by occupation. And what the work is:
the global index of online work demand by occupation over time.

Both come from samples of a handful of platforms. They describe those platforms,
not the whole of platform work, and certainly not all self-employment.
"""
import csv, gzip, json, pathlib, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
RAW  = ROOT/"data/raw/oli"
SLUG = "OII_OLI__DF_ONLINE_GIG"

OCC = [("_T", "All occupations"),
       ("SOFT", "Software development and technology"),
       ("CREA", "Creative and multimedia"),
       ("WRIT", "Writing and translation"),
       ("SALE", "Sales and marketing support"),
       ("PROF", "Professional services"),
       ("CLER", "Clerical and data entry")]
OCC_IN = {"Software development and technology": "SOFT",
          "Creative and multimedia": "CREA", "Writing and translation": "WRIT",
          "Sales and marketing support": "SALE", "Professional services": "PROF",
          "Clerical and data entry": "CLER"}
MEAS = [("SUPPLY_SHARE", "Share of the world's online gig workers", "PT"),
        ("DEMAND_IX", "Global demand for online gig work (index)", "IX16")]
UNITS = [("PT", "Percentage of the world's online gig workers"),
         ("IX16", "Index, 2016 average = 100")]

rec = {}
def put(a, m, o, y, v):
    if v is None: return
    rec.setdefault((a, m, o), {})[y] = v

# ---- supply: annual average worker counts, turned into world shares ----
W = collections.defaultdict(float)          # (area, occ, year) -> workers
for r in csv.DictReader(open(RAW/"oli_workers.csv")):
    o = OCC_IN.get(r["occupation"])
    if not o: continue
    n = float(r["workers"]); y = r["year"]
    W[(r["area"], o, y)] += n
    W[(r["area"], "_T", y)] += n

tot = collections.defaultdict(float)        # (occ, year) -> world total
for (a, o, y), n in W.items(): tot[(o, y)] += n
for (a, o, y), n in W.items():
    T = tot[(o, y)]
    if T > 0: put(a, "SUPPLY_SHARE", o, y, n/T*100)

# ---- demand: the headline index, rebased so 2016 = 100 ----
D = collections.defaultdict(float)
for r in csv.DictReader(open(RAW/"oli_demand.csv")):
    o = OCC_IN.get(r["occupation"])
    if not o: continue
    D[(o, r["year"])] += float(r["index"])
for (o, y), v in list(D.items()): D[("_T", y)] = D.get(("_T", y), 0.0) + v
base = {o: D.get((o, "2016")) for o, _ in OCC}
for (o, y), v in D.items():
    b = base.get(o)
    if b: put("WLD", "DEMAND_IX", o, y, v/b*100)

names = {"WLD": "World"}
for mf in sorted((SITE/"flows").glob("*/meta.json")):
    try: m = json.loads(mf.read_text())
    except Exception: continue
    for d in m.get("dims", []):
        if d.get("id") == "REF_AREA": names.update(dict(zip(d["ids"], d["names"])))

areas = sorted({a for a, _, _ in rec})
occs = [o for o in OCC if any(k[2] == o[0] for k in rec)]
periods = sorted({y for s in rec.values() for y in s}, key=int)
ai = {a: i for i, a in enumerate(areas)}; mi = {m[0]: i for i, m in enumerate(MEAS)}
oi = {o[0]: i for i, o in enumerate(occs)}; ui = {u[0]: i for i, u in enumerate(UNITS)}
mu = {m[0]: m[2] for m in MEAS}; pi = {y: i for i, y in enumerate(periods)}

payload = []
for (a, m, o), s in rec.items():
    ys = sorted(s, key=int)
    payload.append({"k": [ai[a], mi[m], oi[o], ui[mu[m]]],
                    "t": [pi[y] for y in ys], "v": [round(s[y], 4) for y in ys]})

meta = {
 "slug": SLUG, "id": "DF_ONLINE_GIG", "agency": "Oxford Internet Institute",
 "version": "1.0", "name": "Online gig work", "description": "",
 "desc_html": (
   "Platform work is missing from national labor statistics. No labour force survey "
   "counts the Kenyan copywriter working for a London agency through a freelancing "
   "platform, and no OECD table has a column for it. The Online Labour Index, built at "
   "the Oxford Internet Institute, measures it by scraping the platforms directly.<br>"
   "<b>Where the workers are.</b> Each country's share of the world's online "
   "freelancers, and how that share splits by occupation. The distribution is nothing "
   "like the distribution of world income: this is work bought in rich countries and "
   "done in poorer ones, and the occupation dial shows which countries specialize in "
   "software, which in writing, and which in clerical work.<br>"
   "<b>What the work is.</b> The global index of demand for online work by occupation "
   "since 2016, which is where the effect of generative AI on freelance writing and "
   "translation would show up if it were showing up anywhere.<br>"
   "Source: the "
   "<a href=\"http://onlinelabourobservatory.org/\" target=\"_blank\" "
   "rel=\"noopener noreferrer\">Online Labour Observatory</a>, Oxford Internet "
   "Institute and the ILO."),
 "desc_text": "Each country's share of the world's online gig workers by occupation, "
   "and the global index of online work demand since 2016, from the Online Labour Index.",
 "topic": "SOC.SOC_INE",
 "dims": [
   {"id": "REF_AREA", "name": "Country", "ids": areas,
    "names": [names.get(a, a) for a in areas]},
   {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in MEAS],
    "names": [m[1] for m in MEAS], "default": 0},
   {"id": "OCCUPATION", "name": "Occupation", "ids": [o[0] for o in occs],
    "names": [o[1] for o in occs], "default": 0},
   {"id": "UNIT_MEASURE", "name": "Measured as", "ids": [u[0] for u in UNITS],
    "names": [u[1] for u in UNITS]},
 ],
 "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
 "area_dim": "REF_AREA", "layout": "single",
 "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
 "source_url": "http://onlinelabourobservatory.org/",
 "hidden_dims": {},
 "source_notes": [
   "Not an OECD table. Online Labour Index, Oxford Internet Institute and the ILO, "
   "published through the Online Labour Observatory.",
   "The worker figures are a weighted sample of active profiles on Guru, Freelancer, "
   "PeoplePerHour and Fiverr, collected roughly daily and averaged here to annual "
   "figures. They are shown only as shares of the world total, never as counts, because "
   "the underlying numbers are sample sizes rather than population estimates. Countries "
   "are workers' self-declared home countries.",
   "The demand index counts new project postings on the largest English-language "
   "platforms, rebased here so that the 2016 average equals 100. It measures those "
   "platforms rather than the whole online labor market, and it does not cover the "
   "Chinese-language platforms at all.",
   "The first and last years are partial: the index begins in May 2016, which is also "
   "the base the index is rebased on, and the data end in August 2024. Both years are "
   "averages of the days actually observed rather than of a full calendar year, so any "
   "seasonality in online work biases them. The fall in demand for writing and "
   "translation after 2022 is far too large to be a seasonal artefact, but smaller "
   "movements at either end of the series should not be read closely.",
   "Neither series measures gig work done in person -- ride-hailing, delivery, domestic "
   "work -- which is far larger and is not counted anywhere comparable.",
 ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(payload, separators=(",", ":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f'{len(payload)} series, {meta["n_obs"]:,} observations, {len(areas)} areas, '
      f'{periods[0]}-{periods[-1]}')
