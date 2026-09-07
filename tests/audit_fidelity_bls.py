#!/usr/bin/env python3
"""Re-download the BLS flat files and compare all three BLS-sourced datasets."""
import csv, gzip, json, pathlib, urllib.request, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
UA = "ForestAndTheTrees/1.0 (alexthomashoffman@gmail.com)"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=1800).read().decode("utf-8", "replace")

def tsv(text):
    lines = text.splitlines()
    head = [h.strip() for h in lines[0].split("\t")]
    out = []
    for line in lines[1:]:
        c = [x.strip() for x in line.split("\t")]
        c += [""]*(len(head)-len(c))
        out.append(dict(zip(head, c)))
    return out

def load(slug):
    d = ROOT/"site/data/flows"/slug
    m = json.loads((d/"meta.json").read_text())
    r = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
    return m, r

total_m = total_x = 0

# ---- 1. work stoppages, inside the strikes dataset
m, recs = load("ILO__STRIKES")
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
ai = ids.index("REF_AREA")
mi = next(i for i, x in enumerate(m["dims"]) if x["id"] in ("MEASURE", "INDICATOR"))
ours = {}
for r in recs:
    if D["REF_AREA"]["ids"][r["k"][ai]] != "USA": continue
    c = D[ids[mi]]["ids"][r["k"][mi]]
    for t, v in zip(r["t"], r["v"]): ours[(c, P[t])] = v
WS = {"WSU100": "BLS_STOPPAGES", "WSU010": "BLS_WORKERS",
      "WSU001": "BLS_DAYS", "WSU002": "BLS_DAYS_PCT"}
n = x = 0; ex = []
for r in tsv(fetch("https://download.bls.gov/pub/time.series/ws/ws.data.1.AllData")):
    if r.get("period") != "M13" or r["series_id"] not in WS: continue
    try: v = float(r["value"])
    except ValueError: continue
    got = ours.get((WS[r["series_id"]], r["year"]))
    if got is None: continue
    n += 1
    if abs(got - v) > 1e-6:
        x += 1
        if len(ex) < 3: ex.append((WS[r["series_id"]], r["year"], v, got))
print(f"  work stoppages       compared {n:>7,}  mismatched {x}")
for e in ex: print("      ", e)
total_m += n - x; total_x += x

# ---- 2. union membership
m, recs = load("BLS__UNION_MEMBERS")
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
order = ["STATE", "INDY", "OCC", "CLASS", "SEX", "AGE", "RACE", "ORIG", "LFST"]
ours = {}
for r in recs:
    k = tuple([D["MEASURE"]["ids"][r["k"][ids.index("MEASURE")]]] +
              [D[o]["ids"][r["k"][ids.index(o)]] for o in order])
    for t, v in zip(r["t"], r["v"]): ours[(k, P[t])] = v
def measure_of(r):
    if r["earn_code"] == "01":
        return {"0":"EARN_ALL","1":"EARN_MEMBER","2":"EARN_COVERED",
                "3":"EARN_NONUNION"}.get(r["unin_code"])
    pct = r["pcts_code"] == "05"; u = r["unin_code"]
    if u == "1": return "RATE_MEMBER" if pct else "N_MEMBER"
    if u == "2": return "RATE_COVERED" if pct else "N_COVERED"
    if u == "0": return "N_EMPLOYED"
    return None
ser = {r["series_id"].strip(): r for r in tsv(fetch(
    "https://download.bls.gov/pub/time.series/lu/lu.series"))}
n = x = 0; ex = []
for r in tsv(fetch("https://download.bls.gov/pub/time.series/lu/lu.data.1.AllData")):
    if r.get("period") != "A01": continue
    s = ser.get(r["series_id"].strip())
    if not s: continue
    meas = measure_of(s)
    if meas is None: continue
    k = (meas, s["fips_code"] or "00", s["indy_code"] or "0000",
         s["occupation_code"] or "0000", s["class_code"] or "16", s["sexs_code"] or "0",
         s["ages_code"] or "00", s["race_code"] or "00", s["orig_code"] or "00",
         s["lfst_code"] or "20")
    try: v = float(r["value"])
    except ValueError: continue
    got = ours.get((k, r["year"]))
    if got is None: continue
    n += 1
    if abs(got - v) > 1e-6:
        x += 1
        if len(ex) < 3: ex.append((k[:3], r["year"], v, got))
print(f"  union membership     compared {n:>7,}  mismatched {x}")
for e in ex: print("      ", e)
total_m += n - x; total_x += x

# ---- 3. JOLTS
m, recs = load("BLS__JOLTS")
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
order = ["INDY", "STATE", "SIZE"]
ours = {}
for r in recs:
    k = tuple([D["MEASURE"]["ids"][r["k"][ids.index("MEASURE")]]] +
              [D[o]["ids"][r["k"][ids.index(o)]] for o in order])
    for t, v in zip(r["t"], r["v"]): ours[(k, P[t])] = v
ser = {r["series_id"].strip(): r for r in tsv(fetch(
    "https://download.bls.gov/pub/time.series/jt/jt.series"))}
KEEP = {"JO","HI","TS","QU","LD","OS","UO"}
n = x = 0; ex = []
for r in tsv(fetch("https://download.bls.gov/pub/time.series/jt/jt.data.1.AllItems")):
    if r.get("period") != "M13": continue
    s = ser.get(r["series_id"].strip())
    if not s or s["dataelement_code"] not in KEEP: continue
    if s.get("seasonal", "U") != "U": continue
    el = s["dataelement_code"]
    meas = el if el == "UO" else f"{el}_{s['ratelevel_code'] or 'L'}"
    k = (meas, s["industry_code"] or "000000", s["state_code"] or "00",
         s["sizeclass_code"] or "00")
    try: v = float(r["value"])
    except ValueError: continue
    got = ours.get((k, r["year"]))
    if got is None: continue
    n += 1
    if abs(got - v) > 1e-6:
        x += 1
        if len(ex) < 3: ex.append((k[:2], r["year"], v, got))
print(f"  JOLTS                compared {n:>7,}  mismatched {x}")
for e in ex: print("      ", e)
total_m += n - x; total_x += x
print(f"\nBLS: matched {total_m:,}  mismatched {total_x}")
