#!/usr/bin/env python3
"""US union membership by state, industry, occupation and worker type, 1983 on.

The site already carries a national union membership rate for the United States
back to 1917. What it cannot answer is where the membership is: which states,
which industries, public sector against private, and what the union wage premium
looks like once you compare median weekly earnings directly.

BLS publishes all of it annually from 1983. The breakdowns are mutually
exclusive in the source -- a series is cut by state, or by industry, or by
occupation, never by two at once -- so each becomes its own dial and the
interface's availability logic keeps the impossible combinations out of reach.

BLS requires a contact address in the User-Agent for automated access.
"""
import csv, gzip, json, pathlib, urllib.request, collections, re

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SLUG = "BLS__UNION_MEMBERS"
UA = "ForestAndTheTrees/1.0 (alexthomashoffman@gmail.com)"
BASE = "https://download.bls.gov/pub/time.series/lu/"
RAW = ROOT/"data/raw/bls_lu"

def get(name):
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW/name
    if not p.exists():
        req = urllib.request.Request(BASE+name, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=900) as r: p.write_bytes(r.read())
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

def lookup(name, key, val):
    return {r[key]: r[val] for r in tsv(name)}

series = tsv("lu.series")
data = tsv("lu.data.1.AllData")
ST  = lookup("lu.fips", "fips_code", "fips_text")
IND = lookup("lu.indy", "indy_code", "indy_text")
OCC = lookup("lu.occupation", "occupation_code", "occupation_text")
CLS = lookup("lu.class", "class_code", "class_text")
AGE = lookup("lu.ages", "ages_code", "ages_text")
LFS = lookup("lu.lfst", "lfst_code", "lfst_text")
RACE = {"00": "All races", "01": "White", "03": "Black or African American",
        "04": "Asian"}
ORIG = {"00": "All origins", "01": "Hispanic or Latino"}
SEX = {"0": "Total", "1": "Men", "2": "Women"}

def measure_of(r):
    """What the series counts, from the flags BLS sets rather than its prose."""
    # For earnings the union status lives in unin_code, not reliably in the prose:
    # 0 all workers, 1 members, 2 covered by a contract, 3 not represented.
    if r["earn_code"] == "01":
        return {"0": "EARN_ALL", "1": "EARN_MEMBER", "2": "EARN_COVERED",
                "3": "EARN_NONUNION"}.get(r["unin_code"])
    pct = r["pcts_code"] == "05"
    u = r["unin_code"]
    if u == "1": return "RATE_MEMBER" if pct else "N_MEMBER"
    if u == "2": return "RATE_COVERED" if pct else "N_COVERED"
    if u == "0": return "N_EMPLOYED"
    return None

MEASURES = [
  ("RATE_MEMBER",  "Union membership rate",              "PT_EMP"),
  ("RATE_COVERED", "Covered by a union contract",        "PT_EMP"),
  ("N_MEMBER",     "Union members",                      "THS_PER"),
  ("N_COVERED",    "Workers covered by a union contract", "THS_PER"),
  ("N_EMPLOYED",   "Employed",                           "THS_PER"),
  ("EARN_MEMBER",  "Median weekly earnings, union members",     "USD_WK"),
  ("EARN_COVERED", "Median weekly earnings, covered by a contract", "USD_WK"),
  ("EARN_NONUNION","Median weekly earnings, not in a union",     "USD_WK"),
  ("EARN_ALL",     "Median weekly earnings, all workers",        "USD_WK"),
]
UNITS = [("PT_EMP", "Percentage of employed"),
         ("THS_PER", "Thousands of workers"),
         ("USD_WK", "US dollars per week")]

vals = collections.defaultdict(dict)
for d in data:
    if d.get("period") != "A01": continue
    try: v = float(d["value"])
    except (ValueError, KeyError): continue
    vals[d["series_id"].strip()][d["year"]] = v

rec = {}
skipped = 0
for r in series:
    sid = r["series_id"].strip()
    if sid not in vals: continue
    m = measure_of(r)
    if m is None: skipped += 1; continue
    key = (m,
           r["fips_code"] or "00",
           r["indy_code"] or "0000",
           r["occupation_code"] or "0000",
           r["class_code"] or "16",
           r["sexs_code"] or "0",
           r["ages_code"] or "00",
           r["race_code"] or "00",
           r["orig_code"] or "00",
           r["lfst_code"] or "20")
    if key in rec:
        raise SystemExit(f"two series map to one key: {key} ({sid})")
    rec[key] = dict(vals[sid])

def axis(codes, table, total, total_label):
    seen = sorted({c for c in codes})
    out = [(total, total_label)] + [(c, table.get(c, c)) for c in seen if c != total]
    return out

used = list(rec)
AX = {}
AX["STATE"]  = axis({k[1] for k in used}, ST,  "00",   "United States")
AX["INDY"]   = axis({k[2] for k in used}, IND, "0000", "All industries")
AX["OCC"]    = axis({k[3] for k in used}, OCC, "0000", "All occupations")
AX["CLASS"]  = axis({k[4] for k in used}, CLS, "16",   "All wage and salary workers")
AX["SEX"]    = axis({k[5] for k in used}, SEX, "0",    "Total")
AX["AGE"]    = axis({k[6] for k in used}, AGE, "00",   "16 years and over")
AX["RACE"]   = axis({k[7] for k in used}, RACE,"00",   "All races")
AX["ORIG"]   = axis({k[8] for k in used}, ORIG,"00",   "All origins")
AX["LFST"]   = axis({k[9] for k in used}, LFS, "20",   "Employed")

periods = sorted({y for s in rec.values() for y in s}, key=int)
pi = {y: i for i, y in enumerate(periods)}
mi = {m[0]: i for i, m in enumerate(MEASURES)}
ui = {u[0]: i for i, u in enumerate(UNITS)}
mu = {m[0]: m[2] for m in MEASURES}
IDX = {name: {c: i for i, (c, _) in enumerate(ax)} for name, ax in AX.items()}
order = ["STATE", "INDY", "OCC", "CLASS", "SEX", "AGE", "RACE", "ORIG", "LFST"]

payload = []
for key, s in rec.items():
    m = key[0]
    if m not in mi: continue
    ys = sorted(s, key=int)
    k = [0, mi[m]] + [IDX[n][key[i+1]] for i, n in enumerate(order)] + [ui[mu[m]]]
    payload.append({"k": k, "t": [pi[y] for y in ys],
                    "v": [round(s[y], 4) for y in ys]})

NAMES = {"STATE": "State", "INDY": "Industry", "OCC": "Occupation",
         "CLASS": "Type of worker", "SEX": "Sex", "AGE": "Age", "RACE": "Race",
         "ORIG": "Hispanic origin", "LFST": "Hours worked"}
dims = [{"id": "REF_AREA", "name": "Country", "ids": ["USA"],
         "names": ["United States"]},
        {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in MEASURES],
         "names": [m[1] for m in MEASURES], "default": 0}]
for n in order:
    dims.append({"id": n, "name": NAMES[n], "ids": [c for c, _ in AX[n]],
                 "names": [x for _, x in AX[n]], "default": 0})
dims.append({"id": "UNIT_MEASURE", "name": "Measured as",
             "ids": [u[0] for u in UNITS], "names": [u[1] for u in UNITS]})

meta = {
 "slug": SLUG, "id": "LU", "agency": "BLS", "version": "1.0",
 "name": "Union membership in the United States",
 "description": "",
 "desc_html": (
   "Where union membership actually is. The national rate has fallen from 20 per cent in "
   "1983 to about 10 today, but that figure hides almost everything worth knowing: the "
   "public sector is roughly five times as unionised as the private, and the gap between "
   "the most and least unionised states is wider than the gap between countries in "
   "Europe.<br>"
   "The <b>Type of worker</b> dial separates public from private, which is the single "
   "most important cut in American industrial relations. <b>State</b>, <b>Industry</b> "
   "and <b>Occupation</b> are alternative cuts of the same total: the source publishes "
   "each on its own, never crossed, so choosing one returns the others to their total.<br>"
   "Two membership measures are given and they are not the same. Union members are people "
   "who belong. Covered by a union contract includes those working under an agreement "
   "they did not join, which in the United States is a small margin and in much of Europe "
   "is most of the workforce.<br>"
   "Median weekly earnings are given for union members, for those covered by a contract, "
   "and for everyone else, so the raw wage gap can be read directly. It is a raw gap, not "
   "an estimate of what a union is worth: union members are older, more likely to be in "
   "the public sector and better educated. The regression-adjusted premium is in the pay "
   "and productivity table.<br>"
   "Source: US Bureau of Labor Statistics, Union Members series, from the Current "
   "Population Survey."),
 "desc_text": "US union membership and contract coverage by state, industry, occupation "
   "and type of worker, with median weekly earnings for union and non-union workers, "
   "annually from 1983.",
 "topic": "SOC.SOC_INE",
 "dims": dims,
 "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
 "area_dim": "REF_AREA", "layout": "single",
 "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
 "source_url": "https://www.bls.gov/cps/lfcharacteristics.htm#union",
 "hidden_dims": {},
 "source_notes": [
   "Not an OECD table. US Bureau of Labor Statistics, Union Members series, derived from "
   "the Current Population Survey. Annual averages, wage and salary workers only, so the "
   "self-employed are excluded throughout.",
   "State, industry and occupation are alternative cuts of the same population rather "
   "than a grid. The source publishes a series broken down one way at a time, so "
   "selecting a state returns industry and occupation to their totals.",
   "Earnings are median usual weekly earnings of full-time wage and salary workers, in "
   "current dollars, not adjusted for inflation. The difference between union and "
   "non-union earnings here is a raw comparison of two different groups of people, not "
   "the effect of a union on a given worker.",
 ],
}
d = SITE/"flows"/SLUG
d.mkdir(parents=True, exist_ok=True)
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(payload, separators=(",",":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",",":")))
print(f"{len(payload)} series, {meta['n_obs']:,} observations, {periods[0]}-{periods[-1]}")
print(f"skipped {skipped} series whose measure could not be identified")
for n in order: print(f"  {NAMES[n]:16} {len(AX[n]):>3} options")
