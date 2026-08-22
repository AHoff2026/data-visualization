#!/usr/bin/env python3
"""Build a dataset from Our World in Data grapher exports, from a spec.

OWID harmonises long-run historical series that no statistical office publishes
as one table — working hours back to 1870, social spending back to 1880. Those
are the series a question about institutional development actually needs.

  python3 scripts/add_owid_dataset.py <spec-name>
"""
import csv, gzip, json, pathlib, re, sys, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"

SPECS = {
 "hours_longrun": {
   "slug": "OWID__WORKING_HOURS_LONGRUN",
   "name": "Working hours since 1870",
   "topic": "JOBS",
   "desc": ("Average annual hours worked per worker, assembled by Our World in Data "
     "from Huberman and Minns for the historical period and the Penn World Table and "
     "OECD thereafter.<br>No statistical office publishes a series this long. The "
     "fall from roughly three thousand hours a year to under seventeen hundred is the "
     "single largest change in the working life of the period, and it is invisible in "
     "any table that begins in 1970."),
   "series": [("annual-working-hours-per-worker", "working_hours_omm",
               "HOURS", "Annual hours worked per worker", "H", "Hours per year",
               "Huberman & Minns; Penn World Table; OECD")],
 },
 "social_longrun": {
   "slug": "OWID__SOCIAL_SPENDING_LONGRUN",
   "name": "Social spending since 1880",
   "topic": "SOCIAL",
   "desc": ("Public social spending as a share of GDP, from Lindert's historical "
     "series spliced to OECD's social expenditure database by Our World in Data."
     "<br>The modern OECD table begins in 1980, by which time the welfare state was "
     "already built. This one starts in 1880, when public social spending was close "
     "to nothing almost everywhere."),
   "series": [("social-spending-oecd-longrun", "share_gdp",
               "SOCX", "Public social spending", "PT_B1GQ", "Percentage of GDP",
               "Lindert; OECD SOCX")],
 },
 "labor_share": {
   "slug": "OWID__LABOR_SHARE",
   "name": "Labor share of GDP",
   "topic": "WAGE",
   "desc": ("Labor income as a share of GDP — the part of what a country produces "
     "that goes to wages rather than to profit and rent. This is SDG indicator "
     "10.4.1, compiled by the ILO.<br>The labor share is the summary statistic for "
     "the bargain between labor and capital, and it is not published anywhere in "
     "OECD's own statistics."),
   "series": [("labor-share-of-gdp", "_10_4_1__sl_emp_gtotl",
               "LABSH", "Labor share of GDP", "PT_B1GQ", "Percentage of GDP",
               "ILO, via SDG indicator 10.4.1")],
 },
 "labor_rights": {
   "slug": "OWID__LABOR_RIGHTS",
   "name": "Labor rights compliance",
   "topic": "UNION",
   "desc": ("National compliance with labor rights — freedom of association and "
     "collective bargaining — measured against ILO textual sources and national "
     "legislation. This is SDG indicator 8.8.2.<br>A higher score means more "
     "violations, so lower is better: the scale runs from 0 for full compliance "
     "upward."),
   "series": [("level-of-national-compliance-with-labor-rights", "_8_8_2__sl_lbr_ntlcpl",
               "RIGHTS", "Violations of labor rights (0 = full compliance)",
               "IX", "Index", "ILO, via SDG indicator 8.8.2")],
 },
}
BASE = "https://ourworldindata.org/grapher/{}.csv?csvType=full&useColumnShortNames=true"

def fetch(slug):
    req = urllib.request.Request(BASE.format(slug),
        headers={"User-Agent": "ForestAndTheTrees/1.0 (personal research site)"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return list(csv.DictReader(r.read().decode("utf-8").splitlines()))

def build(spec):
    names, records, measures, units, sources = {}, {}, [], [], {}
    for chart, col, mcode, mname, ucode, uname, src in spec["series"]:
        rows = fetch(chart)
        if mcode not in [m[0] for m in measures]: measures.append((mcode, mname))
        if ucode not in [u[0] for u in units]: units.append((ucode, uname))
        sources[mname] = src
        kept = 0
        for r in rows:
            code = (r.get("code") or "").strip()
            if not re.fullmatch(r"[A-Z]{3}", code): continue      # ISO3 only
            v = (r.get(col) or "").strip()
            if not v: continue
            try: val = float(v)
            except ValueError: continue
            names.setdefault(code, r["entity"])
            records.setdefault((code, mcode, ucode), {})[r["year"]] = val
            kept += 1
        print(f"  {chart:56} {kept:6} observations")

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
      "slug": spec["slug"], "id": spec["slug"].split("__")[-1], "agency": "OWID",
      "version": "1.0", "name": spec["name"], "description": "",
      "desc_html": spec["desc"],
      "desc_text": re.sub(r"<[^>]+>", " ", spec["desc"]),
      "topic": spec["topic"],
      "dims": [
        {"id": "REF_AREA", "name": "Country", "ids": area_ids,
         "names": [names[a] for a in area_ids]},
        {"id": "MEASURE", "name": "Indicator",
         "ids": [m[0] for m in measures], "names": [m[1] for m in measures]},
        {"id": "UNIT_MEASURE", "name": "Measured as",
         "ids": [u[0] for u in units], "names": [u[1] for u in units]},
      ],
      "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
      "area_dim": "REF_AREA", "layout": "single", "hidden_dims": {},
      "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
      "source_url": "https://ourworldindata.org/",
      "source_notes": ["Not an OECD table. " +
        "; ".join(f"{k} — {v}" for k, v in sources.items()) +
        ", assembled and harmonised by Our World in Data."],
    }
    d = SITE/"flows"/spec["slug"]; d.mkdir(parents=True, exist_ok=True)
    (d/"all.json.gz").write_bytes(gzip.compress(
        json.dumps(payload, separators=(",", ":")).encode(), 6))
    (d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    print(f'  -> {meta["n_series"]} series, {meta["n_obs"]:,} observations, '
          f'{len(area_ids)} countries, {periods[0]}-{periods[-1]}')

for key in (sys.argv[1:] or SPECS):
    print(f"building {key}")
    build(SPECS[key])
