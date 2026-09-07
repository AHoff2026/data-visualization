#!/usr/bin/env python3
"""Re-download the ILOSTAT strike flows and compare them to what we serve."""
import csv, gzip, io, json, pathlib, re, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
BASE = "https://sdmx.ilo.org/rest/data/ILO,{},1.0/all?format=csv"
FLOWS = [("DF_STR_DAYS_ECO_RT","DAYS_RT"),("DF_STR_DAYS_ECO_NB","DAYS_NB"),
         ("DF_STR_TSTR_ECO_NB","STRIKES"),("DF_STR_WORK_ECO_NB","WORKERS")]
ECO_TOTAL = re.compile(r"^ECO_(AGGREGATE_TOTAL|SECTOR_TOTAL)$|^_T$|TOTAL", re.I)

d = ROOT/"site/data/flows/ILO__STRIKES"
m = json.loads((d/"meta.json").read_text())
recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
ai = ids.index("REF_AREA")
mi = next(i for i, x in enumerate(m["dims"]) if x["id"] in ("MEASURE", "INDICATOR"))
ours = {}
for r in recs:
    k = (D["REF_AREA"]["ids"][r["k"][ai]], D[ids[mi]]["ids"][r["k"][mi]])
    for t, v in zip(r["t"], r["v"]): ours[(k, P[t])] = v
site_areas = set(D["REF_AREA"]["ids"])

tot_m = tot_x = 0
for flow, code in FLOWS:
    req = urllib.request.Request(BASE.format(flow), headers={
        "Accept": "application/vnd.sdmx.data+csv;version=1.0.0",
        "User-Agent": "ForestAndTheTrees/1.0"})
    rows = list(csv.DictReader(io.StringIO(
        urllib.request.urlopen(req, timeout=1200).read().decode("utf-8", "replace"))))
    n = x = 0
    ex = []
    for r in rows:
        if not r.get("OBS_VALUE"): continue
        if r.get("FREQ") not in (None, "A"): continue
        eco = r.get("ECO") or r.get("CLASSIF1") or "_T"
        if not ECO_TOTAL.search(eco): continue
        a = (r.get("REF_AREA") or "").strip()
        if a not in site_areas: continue
        got = ours.get(((a, code), r.get("TIME_PERIOD")))
        if got is None: continue
        try: v = float(r["OBS_VALUE"])
        except ValueError: continue
        n += 1
        if abs(got - v) > max(1e-6, abs(v)*1e-9):
            x += 1
            if len(ex) < 3: ex.append((a, code, r["TIME_PERIOD"], v, got))
    print(f"  {flow:26} compared {n:>6,}  mismatched {x}")
    for e in ex: print("      ", e)
    tot_m += n - x; tot_x += x
print(f"\nILOSTAT strikes: matched {tot_m:,}  mismatched {tot_x}")
