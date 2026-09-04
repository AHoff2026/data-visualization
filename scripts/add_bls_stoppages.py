#!/usr/bin/env python3
"""US work stoppages from BLS, 1947 onward, merged into the strikes dataset.

ILOSTAT's United States series begins in 1974, which is after the peak and so
cuts off the thing worth seeing. BLS has run the Work Stoppages programme since
1947: 470 major stoppages in 1952, 424 as late as 1974, then 145 in 1981, 44 by
1990, 11 in 2010. A series that starts in 1974 shows a decline; one that starts
in 1947 shows what was lost.

ILOSTAT's United States submission turns out to be this same BLS series: where the
two overlap they agree to within a unit or two. They are kept as separate
indicators anyway, because the BLS one reaches back twenty-seven further years.

BLS asks for a contact address in the User-Agent, which is their documented
condition for automated access.
"""
import csv, gzip, io, json, pathlib, urllib.request, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SLUG = "ILO__STRIKES"
UA = "ForestAndTheTrees/1.0 (alexthomashoffman@gmail.com)"
SRC = "https://download.bls.gov/pub/time.series/ws/ws.data.1.AllData"

# BLS series -> (code, display name, unit code, unit name)
SERIES = {
    "WSU100": ("BLS_STOPPAGES", "Major work stoppages beginning in the year (BLS)",
               "NB", "Number of stoppages"),
    "WSU010": ("BLS_WORKERS", "Workers involved in major stoppages (BLS)",
               "THS_PER", "Thousands of workers"),
    "WSU001": ("BLS_DAYS", "Days of idleness from major stoppages (BLS)",
               "THS_DAY", "Thousands of days"),
    "WSU002": ("BLS_DAYS_PCT", "Days of idleness as a share of working time (BLS)",
               "PT_TIME", "Percentage of total working time"),
}

def fetch():
    req = urllib.request.Request(SRC, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read().decode("utf-8", "replace")

raw = fetch()
vals = collections.defaultdict(dict)
for r in csv.DictReader(io.StringIO(raw), delimiter="\t"):
    r = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in r.items()}
    if r.get("period") != "M13" or r["series_id"] not in SERIES: continue
    try: vals[r["series_id"]][r["year"]] = float(r["value"])
    except (ValueError, KeyError): pass
print("BLS annual points: " + ", ".join(f"{k}={len(v)}" for k, v in vals.items()))

d = ROOT/"site/data/flows"/SLUG
meta = json.loads((d/"meta.json").read_text())
recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
ids = [x["id"] for x in meta["dims"]]
D = {x["id"]: x for x in meta["dims"]}
ai, ui = ids.index("REF_AREA"), ids.index("UNIT_MEASURE")
mi = next(i for i, x in enumerate(meta["dims"]) if x["id"] in ("MEASURE", "INDICATOR"))

def ensure(dim, code, name):
    if code not in dim["ids"]:
        dim["ids"].append(code); dim["names"].append(name)
    return dim["ids"].index(code)

if "USA" not in D["REF_AREA"]["ids"]:
    raise SystemExit("United States absent from the strikes dataset")
a_us = D["REF_AREA"]["ids"].index("USA")
periods = list(meta["periods"])
added = 0
for sid, (code, name, ucode, uname) in SERIES.items():
    if not vals.get(sid): continue
    m_idx = ensure(meta["dims"][mi], code, name)
    u_idx = ensure(meta["dims"][ui], ucode, uname)
    for y in vals[sid]:
        if y not in periods: periods.append(y)
    periods_sorted = sorted(set(periods), key=int)
    k = [0]*len(meta["dims"])
    k[ai], k[mi], k[ui] = a_us, m_idx, u_idx
    for i, dim in enumerate(meta["dims"]):
        if i not in (ai, mi, ui): k[i] = dim.get("default", 0)
    ys = sorted(vals[sid], key=int)
    recs.append({"k": k, "t": [periods_sorted.index(y) for y in ys],
                 "v": [round(vals[sid][y], 4) for y in ys]})
    added += len(ys)
    periods = periods_sorted

# every existing record's period indices must move to the new axis
old = meta["periods"]
if periods != old:
    remap = {i: periods.index(p) for i, p in enumerate(old)}
    for r in recs[:-len([s for s in SERIES if vals.get(s)])]:
        r["t"] = [remap[t] for t in r["t"]]
meta["periods"] = periods
meta["n_series"] = len(recs)
meta["n_obs"] = sum(len(r["v"]) for r in recs)
notes = meta.get("source_notes") or []
n = ("The United States appears from two sources. ILOSTAT carries the national "
     "submission from 1974; the BLS series, marked as such, run from 1947. Where the "
     "two overlap they agree almost exactly, because ILOSTAT's United States "
     "submission is this same BLS count of stoppages involving a thousand workers or "
     "more: 424 against 425 in 1974, 44 against 44 in 1990. BLS is included for the "
     "twenty-seven earlier years, which hold the peak.")
if not any("appears from two sources" in x for x in notes):
    notes.append(n); meta["source_notes"] = notes
(d/"all.json.gz").write_bytes(gzip.compress(json.dumps(recs, separators=(",", ":")).encode(), 6))
(d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f"added {added:,} observations; dataset now {meta['n_obs']:,} obs, "
      f"{periods[0]}-{periods[-1]}")
