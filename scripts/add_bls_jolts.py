#!/usr/bin/env python3
"""Job openings, hires, quits and layoffs in the United States, 2000 on.

The quits rate is the closest thing there is to a direct measure of worker
bargaining power. People leave jobs voluntarily when they believe another one is
available and when the one they have is not worth keeping; they stop when they
do not. Nothing else on this site captures that, and the series runs from 2000,
through the collapse of 2009 and the peak of 2021 and 2022.

Annual averages are used. The monthly file is on disk and the story is the same
shape, but a monthly line across twenty-six years is noise a reader has to see
through rather than information.

BLS requires a contact address in the User-Agent for automated access.
"""
import csv, gzip, json, pathlib, urllib.request, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SLUG = "BLS__JOLTS"
UA = "ForestAndTheTrees/1.0 (alexthomashoffman@gmail.com)"
BASE = "https://download.bls.gov/pub/time.series/jt/"
RAW = ROOT/"data/raw/bls_jt"

def get(name):
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW/name
    if not p.exists():
        req = urllib.request.Request(BASE+name, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=1800) as r: p.write_bytes(r.read())
    return p

def tsv(name):
    with open(get(name)) as f:
        head = [h.strip() for h in f.readline().rstrip("\n").split("\t")]
        rows = []
        for line in f:
            c = [x.strip() for x in line.rstrip("\n").split("\t")]
            c += [""]*(len(head)-len(c))
            rows.append(dict(zip(head, c)))
    return rows

lk = lambda n, k, v: {r[k]: r[v] for r in tsv(n)}
ELEM = lk("jt.dataelement", "dataelement_code", "dataelement_text")
IND  = lk("jt.industry", "industry_code", "industry_text")
STA  = lk("jt.state", "state_code", "state_text")
SIZ  = lk("jt.sizeclass", "sizeclass_code", "sizeclass_text")

# Response rates are survey admin, not labour market. The unemployed-per-opening
# ratio has no level/rate distinction and is kept as its own measure.
KEEP = {"JO", "HI", "TS", "QU", "LD", "OS", "UO"}
NICE = {"JO": "Job openings", "HI": "Hires", "TS": "Separations, total",
        "QU": "Quits", "LD": "Layoffs and discharges",
        "OS": "Other separations", "UO": "Unemployed people per job opening"}

vals = collections.defaultdict(dict)
for d in tsv("jt.data.1.AllItems"):
    if d.get("period") != "M13": continue          # annual average
    try: vals[d["series_id"].strip()][d["year"]] = float(d["value"])
    except (ValueError, KeyError): pass

rec = {}
for r in tsv("jt.series"):
    sid = r["series_id"].strip()
    if sid not in vals: continue
    el = r["dataelement_code"]
    if el not in KEEP: continue
    if r.get("seasonal", "U") != "U": continue     # unadjusted; annual means anyway
    lvl = r["ratelevel_code"] or "L"
    meas = el if el == "UO" else f"{el}_{lvl}"
    key = (meas, r["industry_code"] or "000000",
           r["state_code"] or "00", r["sizeclass_code"] or "00")
    if key in rec: raise SystemExit(f"two series map to one key: {key} ({sid})")
    rec[key] = dict(vals[sid])

MEAS = []
for el in ["JO", "HI", "QU", "TS", "LD", "OS"]:
    MEAS.append((f"{el}_R", f"{NICE[el]}, rate", "PT_EMP"))
    MEAS.append((f"{el}_L", f"{NICE[el]}, number", "THS_PER"))
MEAS.append(("UO", NICE["UO"], "RATIO"))
MEAS = [m for m in MEAS if any(k[0] == m[0] for k in rec)]
UNITS = [("PT_EMP", "Percentage of employment"), ("THS_PER", "Thousands of people"),
         ("RATIO", "People per opening")]

def axis(vals_, table, total, label):
    seen = sorted(vals_)
    return [(total, label)] + [(c, table.get(c, c)) for c in seen if c != total]

AX = {"INDY":  axis({k[1] for k in rec}, IND, "000000", "All industries"),
      "STATE": axis({k[2] for k in rec}, STA, "00", "United States"),
      "SIZE":  axis({k[3] for k in rec}, SIZ, "00", "All firm sizes")}
order = ["INDY", "STATE", "SIZE"]
NAMES = {"INDY": "Industry", "STATE": "State", "SIZE": "Size of firm"}

periods = sorted({y for s in rec.values() for y in s}, key=int)
pi = {y: i for i, y in enumerate(periods)}
mi = {m[0]: i for i, m in enumerate(MEAS)}
ui = {u[0]: i for i, u in enumerate(UNITS)}
mu = {m[0]: m[2] for m in MEAS}
IDX = {n: {c: i for i, (c, _) in enumerate(AX[n])} for n in order}

payload = []
for key, s in rec.items():
    if key[0] not in mi: continue
    ys = sorted(s, key=int)
    k = [0, mi[key[0]]] + [IDX[n][key[i+1]] for i, n in enumerate(order)] + [ui[mu[key[0]]]]
    payload.append({"k": k, "t": [pi[y] for y in ys], "v": [round(s[y], 4) for y in ys]})

dims = [{"id": "REF_AREA", "name": "Country", "ids": ["USA"], "names": ["United States"]},
        {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in MEAS],
         "names": [m[1] for m in MEAS],
         "default": next((i for i, m in enumerate(MEAS) if m[0] == "QU_R"), 0)}]
for n in order:
    dims.append({"id": n, "name": NAMES[n], "ids": [c for c, _ in AX[n]],
                 "names": [x for _, x in AX[n]], "default": 0})
dims.append({"id": "UNIT_MEASURE", "name": "Measured as", "ids": [u[0] for u in UNITS],
             "names": [u[1] for u in UNITS]})

meta = {
 "slug": SLUG, "id": "JT", "agency": "BLS", "version": "1.0",
 "name": "Job openings, hires and quits (United States)",
 "description": "",
 "desc_html": (
   "How much movement there is in the American labor market, and who is choosing it. "
   "The <b>quits rate</b> is the measure worth starting from: it counts people leaving "
   "jobs voluntarily, which they do when they believe another job is there and stop doing "
   "when they do not. It halved in the crisis of 2009, climbed through the 2010s, and "
   "reached its highest level on record in 2021 and 2022 before falling back.<br>"
   "Read against layoffs, it separates two very different labor markets that produce "
   "similar turnover: one where firms are shedding workers and one where workers are "
   "leaving. Read against job openings, it says whether people are quitting into "
   "opportunity or out of exhaustion.<br>"
   "Every measure comes as a rate and as a number of people. The rate is the one to "
   "compare across industries and over time; the count is dominated by how large the "
   "sector is.<br>"
   "Source: US Bureau of Labor Statistics, Job Openings and Labor Turnover Survey."),
 "desc_text": "US job openings, hires, quits and layoffs by industry, state and firm "
   "size, annually from 2000. The quits rate is the closest available measure of worker "
   "bargaining power.",
 "topic": "SOC.SOC_INE",
 "dims": dims,
 "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
 "area_dim": "REF_AREA", "layout": "single",
 "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
 "source_url": "https://www.bls.gov/jlt/",
 "hidden_dims": {},
 "source_notes": [
   "Not an OECD table. US Bureau of Labor Statistics, Job Openings and Labor Turnover "
   "Survey. Annual averages of the unadjusted monthly series; the monthly detail exists "
   "in the source for anyone who needs the turning points precisely.",
   "Rates are the count for the month as a percentage of employment, so a quits rate of "
   "2.4 means that in an average month about one worker in forty left voluntarily. Over "
   "a year that is a much larger share of the workforce than the monthly figure suggests.",
   "Industry, state and firm size are alternative cuts rather than a grid, so choosing "
   "one returns the others to their totals.",
 ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(payload, separators=(",",":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",",":")))
print(f"{len(payload)} series, {meta['n_obs']:,} observations, {periods[0]}-{periods[-1]}")
for n in order: print(f"  {NAMES[n]:14} {len(AX[n]):>3} options")
