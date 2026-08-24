#!/usr/bin/env python3
"""Re-fetch a sample of series from the original API and compare to what we serve.

The claim this checks is that a number shown on the site is the number the source
published: not rescaled, not rounded, not re-based. It re-downloads a slice from
the live service and compares value for value.
"""
import json, gzip, pathlib, urllib.request, io, csv, random, sys

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
random.seed(11)

def load(slug):
    d = FLOWS/slug; m = json.loads((d/"meta.json").read_text())
    recs = []
    if m["layout"] == "single":
        recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
    else:
        for f in sorted((d/"parts").glob("*.json.gz")):
            recs += json.loads(gzip.decompress(f.read_bytes()))
    return m, recs

def oecd(agency, flow, key, lo="2015", hi="2016"):
    url = (f"https://sdmx.oecd.org/public/rest/data/{agency},{flow},/all"
           f"?format=csvfilewithlabels&startPeriod={lo}&endPeriod={hi}")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.sdmx.data+csv; charset=utf-8; labels=both",
        "Accept-Encoding": "gzip", "User-Agent": "ForestAndTheTrees/1.0"})
    with urllib.request.urlopen(req, timeout=900) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
    return list(csv.DictReader(io.StringIO(b.decode())))

# A spread of sources and shapes: a small table, a ratio table, a big partitioned
# one, a tax table and a national-accounts table.
CASES = []
for slug in ["OECD.ELS.SAE__DF_TUD", "OECD.ELS.SAE__DEC_I", "OECD.ELS.SPD__DF_SOCX_AGG",
             "OECD.ELS.SAE__DF_TUD", "OECD.WISE.INE__DF_IDD", "OECD.ELS.SAE__RMW",
             "OECD.ELS.JAI__DF_EPL", "OECD.SDD.TPS__DF_PDB"]:
    mp = FLOWS/slug/"meta.json"
    if not mp.exists(): continue
    mm = json.loads(mp.read_text())
    CASES.append((slug, mm["agency"], mm["id"], None))
seen = set(); CASES = [c for c in CASES if not (c[0] in seen or seen.add(c[0]))]

total_checked = total_bad = 0
for slug, agency, flow, key in CASES:
    if not (FLOWS/slug).exists(): print(f"  {slug}: not present"); continue
    m, recs = load(slug)
    ids = [x["id"] for x in m["dims"]]
    P = m["periods"]
    ours = {}
    D = {x["id"]: x for x in m["dims"]}
    for r in recs:
        k = tuple(D[ids[i]]["ids"][v] for i, v in enumerate(r["k"]))
        for t, v in zip(r["t"], r["v"]): ours[(k, P[t])] = v
    try: rows = oecd(agency, flow, key)
    except Exception as e: print(f"  {slug}: fetch failed {e}"); continue
    checked = bad = 0; misses = []
    for row in rows:
        if not row.get("OBS_VALUE"): continue
        try: k = tuple(row[i] for i in ids)
        except KeyError: continue
        got = ours.get((k, row["TIME_PERIOD"]))
        if got is None: continue
        src = float(row["OBS_VALUE"])
        checked += 1
        if abs(got - src) > max(1e-6, abs(src)*1e-9):
            bad += 1
            if len(misses) < 3: misses.append((k, row["TIME_PERIOD"], src, got))
    total_checked += checked; total_bad += bad
    print(f"  {m['name'][:40]:42} checked {checked:>7,}  mismatched {bad}")
    for k, t, s, g in misses: print(f"        {k} {t}: source {s} vs site {g}")
print(f"\ntotal compared {total_checked:,}   mismatches {total_bad}")
sys.exit(1 if total_bad else 0)
