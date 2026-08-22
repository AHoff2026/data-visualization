#!/usr/bin/env python3
"""Build the OECD/AIAS ICTWSS institutional dataset.

OECD's SDMX service publishes only two of this database's variables — union
density and bargaining coverage. The rest of it, which is the part about
institutions rather than membership, exists only as a spreadsheet: at what level
wage bargaining happens, whether agreements are extended to non-signatories, how
wage setting is coordinated, whether works councils bargain, whether a tripartite
council exists.
"""
import gzip, json, pathlib, re, urllib.request
import openpyxl

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SLUG = "OECD_AIAS__ICTWSS"
URL = ("https://www.oecd.org/content/dam/oecd/en/topics/policy-sub-issues/"
       "collective-bargaining-and-social-dialogue/oecd-aias-ictwss_v1.1.xlsx")

# variable -> (unit code, unit label). Scales are ordinal codes defined by the
# source; the variable label says what the scale measures.
UNITS = {
    "UD_hist":    ("PT_SAL", "Percentage of employees"),
    "AdjCov_hist":("PT_SAL", "Percentage of employees"),
    "ED":         ("PT_EMPR", "Percentage of employers"),
}
SCALE = ("SCALE", "Ordinal scale (see the indicator description)")

def main():
    raw = ROOT/"raw"; raw.mkdir(exist_ok=True)
    xf = raw/"ictwss.xlsx"
    if not xf.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "ForestAndTheTrees/1.0"})
        with urllib.request.urlopen(req, timeout=600) as r: xf.write_bytes(r.read())
    wb = openpyxl.load_workbook(xf, read_only=True, data_only=True)
    rows = list(wb["Core variables"].iter_rows(values_only=True))
    groups, codes, labels = rows[1], rows[2], rows[3]
    data = rows[4:]

    var_cols = [i for i in range(3, len(codes)) if codes[i]]
    measures = [(str(codes[i]), f"{str(labels[i]).strip()}") for i in var_cols]
    units = []
    for c, _ in measures:
        u = UNITS.get(c, SCALE)
        if u not in units: units.append(u)

    names, records = {}, {}
    for r in data:
        iso = str(r[1]).strip() if r[1] else ""
        if not re.fullmatch(r"[A-Z]{3}", iso): continue
        try: year = str(int(r[2]))
        except (TypeError, ValueError): continue
        names.setdefault(iso, str(r[0]).strip())
        for i in var_cols:
            v = r[i]
            if v is None: continue
            try: val = float(str(v).strip())
            except (TypeError, ValueError): continue
            # ICTWSS marks absent information with negative sentinels: -88 is
            # "not applicable", -99 "no information". They are not measurements.
            if val <= -80: continue
            mc = str(codes[i]); uc = UNITS.get(mc, SCALE)[0]
            records.setdefault((iso, mc, uc), {})[year] = val

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

    defs = {str(codes[i]): f"{str(groups[i]).strip()} — {str(labels[i]).strip()}"
            for i in var_cols}
    meta = {
      "slug": SLUG, "id": "ICTWSS", "agency": "OECD/AIAS", "version": "1.1",
      "name": "Bargaining institutions (ICTWSS)",
      "description": "",
      "desc_html": ("The institutional half of the OECD/AIAS ICTWSS database: at what "
        "level wage bargaining takes place, whether agreements are extended by law to "
        "firms that never signed them, how wage setting is coordinated across sectors, "
        "whether works councils bargain over pay, and whether a tripartite council "
        "exists.<br>OECD's statistical service publishes only two variables from this "
        "database, union density and bargaining coverage. The rest is distributed as a "
        "spreadsheet and is not in any SDMX service. Most of these indicators are "
        "ordinal codes defined by the source rather than quantities; the indicator "
        "description says what each scale measures."),
      "desc_text": "The institutional half of the OECD/AIAS ICTWSS database: bargaining "
        "level, mandatory extension, wage coordination, works councils and tripartite "
        "councils.",
      "topic": "UNION",
      "dims": [
        {"id": "REF_AREA", "name": "Country", "ids": area_ids,
         "names": [names[a] for a in area_ids]},
        {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in measures],
         "names": [m[1] for m in measures], "code_defs": defs},
        {"id": "UNIT_MEASURE", "name": "Measured as", "ids": [u[0] for u in units],
         "names": [u[1] for u in units]},
      ],
      "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
      "area_dim": "REF_AREA", "layout": "single", "hidden_dims": {},
      "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
      "source_url": "https://www.oecd.org/en/data/datasets/oecdaias-ictwss-database.html",
      "source_notes": [
        "OECD/AIAS ICTWSS version 1.1, read from the published spreadsheet. Most "
        "indicators here are ordinal codes, not quantities: a higher bargaining level "
        "means a different level, not more of something. Read them as categories "
        "changing over time, and consult the source for what each code means.",
      ],
    }
    d = SITE/"flows"/SLUG; d.mkdir(parents=True, exist_ok=True)
    (d/"all.json.gz").write_bytes(gzip.compress(
        json.dumps(payload, separators=(",", ":")).encode(), 6))
    (d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    xf.unlink(missing_ok=True)
    print(f'{meta["n_series"]} series, {meta["n_obs"]:,} observations, '
          f'{len(area_ids)} countries, {periods[0]}-{periods[-1]}')
    print(f'indicators: {len(measures)}')
    for c, l in measures: print(f'   {c:14} {l[:66]}')

main()
