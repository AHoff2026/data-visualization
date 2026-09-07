#!/usr/bin/env python3
"""Re-download the ICTWSS spreadsheet and compare it to what we serve.

ICTWSS is on no SDMX service; it is a single CSV published by OECD. That makes
it the dataset most likely to drift unnoticed, so it gets compared against a
fresh download of that same file.
"""
import csv, gzip, io, json, pathlib, urllib.request, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SRC = "https://webfs.oecd.org/Els-com/ICTWSS-Database/ICTWSS_v2.csv"
SLUG = "OECD_AIAS__ICTWSS"

req = urllib.request.Request(SRC, headers={"User-Agent": "ForestAndTheTrees/1.0"})
raw = urllib.request.urlopen(req, timeout=1800).read().decode("utf-8", "replace")
rows = list(csv.DictReader(io.StringIO(raw)))
print(f"source rows: {len(rows):,}   columns: {len(rows[0])}")

d = ROOT/"site/data/flows"/SLUG
m = json.loads((d/"meta.json").read_text())
recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
ids = [x["id"] for x in m["dims"]]
D = {x["id"]: x for x in m["dims"]}
P = m["periods"]
ai, mi = ids.index("REF_AREA"), ids.index("MEASURE")
ours = {}
for r in recs:
    a = D["REF_AREA"]["ids"][r["k"][ai]]
    v = D["MEASURE"]["ids"][r["k"][mi]]
    for t, val in zip(r["t"], r["v"]): ours[(a, v, P[t])] = val

# The source is one row per country-year, one column per variable.
iso = next((c for c in rows[0] if c.lower() in ("iso3", "iso_3", "country_code")), None)
yr  = next((c for c in rows[0] if c.lower() in ("year", "yr")), None)
print(f"country column: {iso}   year column: {yr}")
SENTINEL = {-88.0, -99.0}
matched = mism = absent = 0
ex = []
codes = set(D["MEASURE"]["ids"])
for r in rows:
    a = (r.get(iso) or "").strip().upper()
    y = (r.get(yr) or "").strip()
    if not a or not y: continue
    for col, val in r.items():
        if col not in codes or val in ("", None): continue
        try: f = float(val)
        except ValueError: continue
        if f in SENTINEL: continue        # documented "not applicable" / "no information"
        got = ours.get((a, col, y))
        if got is None: absent += 1; continue
        if abs(got - f) > max(1e-6, abs(f)*1e-9):
            mism += 1
            if len(ex) < 5: ex.append((a, col, y, f, got))
        else: matched += 1
print(f"\nmatched {matched:,}   mismatched {mism}   on site but not compared {absent:,}")
for e in ex: print("   source vs site:", e)
