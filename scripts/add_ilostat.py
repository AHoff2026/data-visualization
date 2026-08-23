#!/usr/bin/env python3
"""Build a strike-activity dataset from ILOSTAT's SDMX service.

Strikes are associational power in action, and there is nothing like them in
OECD's statistics. ILOSTAT publishes days not worked, the number of stoppages,
and the number of workers involved, with a per-thousand-workers rate that is the
only one of the four comparable across countries of different size.
"""
import csv, gzip, io, json, pathlib, re, urllib.request
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SLUG = "ILO__STRIKES"
BASE = "https://sdmx.ilo.org/rest/data/ILO,{},1.0/all?format=csv"

FLOWS = [
    ("DF_STR_DAYS_ECO_RT", "DAYS_RT",
     "Days not worked per 1000 workers", "RT1000", "Days per 1,000 workers"),
    ("DF_STR_DAYS_ECO_NB", "DAYS_NB",
     "Days not worked due to strikes and lockouts", "DAYS", "Days"),
    ("DF_STR_TSTR_ECO_NB", "STRIKES",
     "Number of strikes and lockouts", "NB", "Count"),
    ("DF_STR_WORK_ECO_NB", "WORKERS",
     "Workers involved in strikes and lockouts", "PS", "Number of people"),
]
ECO_TOTAL = re.compile(r"^ECO_(AGGREGATE_TOTAL|SECTOR_TOTAL)$|^_T$|TOTAL", re.I)

def fetch(flow):
    url = BASE.format(flow)
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.sdmx.data+csv;version=1.0.0",
        "User-Agent": "ForestAndTheTrees/1.0"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return list(csv.DictReader(io.StringIO(r.read().decode("utf-8", "replace"))))

def main():
    names, records = {}, {}
    measures, units = [], []
    for flow, mcode, mname, ucode, uname in FLOWS:
        rows = fetch(flow)
        if mcode not in [m[0] for m in measures]: measures.append((mcode, mname))
        if ucode not in [u[0] for u in units]: units.append((ucode, uname))
        kept = 0
        for r in rows:
            area = (r.get("REF_AREA") or "").strip()
            if not re.fullmatch(r"[A-Z]{3}", area): continue      # ISO3 only
            if (r.get("FREQ") or "A") != "A": continue            # annual
            eco = (r.get("ECO") or "").strip()
            if eco and not ECO_TOTAL.search(eco): continue        # whole economy only
            v = (r.get("OBS_VALUE") or "").strip()
            if not v: continue
            try: val = float(v)
            except ValueError: continue
            year = (r.get("TIME_PERIOD") or "").strip()[:4]
            if not year.isdigit(): continue
            names.setdefault(area, area)
            records.setdefault((area, mcode, ucode), {})[year] = val
            kept += 1
        print(f"  {flow:22} {kept:7} observations")

    # country names from the catalog's lookup, falling back to the code
    cat = json.loads((SITE/"catalog.json").read_text())
    lookup = cat.get("area_names", {})
    for a in names: names[a] = lookup.get(a, a)

    area_ids = sorted(names)
    periods = sorted({y for d in records.values() for y in d}, key=int)
    pidx = {y: i for i, y in enumerate(periods)}
    aidx = {a: i for i, a in enumerate(area_ids)}
    midx = {m[0]: i for i, m in enumerate(measures)}
    uidx = {u[0]: i for i, u in enumerate(units)}
    payload = []
    for (a, m, u), s in records.items():
        ys = sorted(s, key=int)
        payload.append({"k": [aidx[a], midx[m], uidx[u]],
                        "t": [pidx[y] for y in ys], "v": [round(s[y], 6) for y in ys]})

    meta = {
      "slug": SLUG, "id": "STRIKES", "agency": "ILOSTAT", "version": "1.0",
      "name": "Strikes and lockouts",
      "description": "",
      "desc_html": ("Days not worked, stoppages and workers involved in strikes and "
        "lockouts, from ILOSTAT.<br>Nothing like this exists in OECD's statistics. "
        "Strikes are the exercise of associational power rather than its stock, and the "
        "counts move on events rather than trends: a single national dispute can lift a "
        "country's figure by an order of magnitude for one year.<br>Use days not worked "
        "per thousand workers for comparison between countries; the raw counts mostly "
        "measure how large the workforce is."),
      "desc_text": "Days not worked, stoppages and workers involved in strikes and "
        "lockouts, from ILOSTAT, for the whole economy.",
      "topic": "UNION",
      "dims": [
        {"id": "REF_AREA", "name": "Country", "ids": area_ids,
         "names": [names[a] for a in area_ids]},
        {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in measures],
         "names": [m[1] for m in measures]},
        {"id": "UNIT_MEASURE", "name": "Measured as", "ids": [u[0] for u in units],
         "names": [u[1] for u in units]},
      ],
      "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
      "area_dim": "REF_AREA", "layout": "single", "hidden_dims": {},
      "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
      "source_url": "https://ilostat.ilo.org/data/",
      "source_notes": [
        "ILOSTAT, whole economy and annual frequency only; the source also breaks these "
        "down by economic activity. National statistical definitions of a reportable "
        "stoppage differ - some countries exclude disputes below a size or duration "
        "threshold - so levels are less comparable between countries than movements are "
        "within one.",
      ],
    }
    d = SITE/"flows"/SLUG; d.mkdir(parents=True, exist_ok=True)
    (d/"all.json.gz").write_bytes(gzip.compress(
        json.dumps(payload, separators=(",", ":")).encode(), 6))
    (d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    print(f'{meta["n_series"]} series, {meta["n_obs"]:,} observations, '
          f'{len(area_ids)} countries, {periods[0]}-{periods[-1]}')

main()
