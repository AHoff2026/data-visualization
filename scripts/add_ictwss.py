#!/usr/bin/env python3
"""Build the OECD/AIAS ICTWSS institutional dataset, version 2.0.

OECD's SDMX service publishes two variables from this database — union density
and bargaining coverage. The rest, which is the part about institutions rather
than membership, is distributed as a spreadsheet and appears in no SDMX service
anywhere: at what level bargaining happens, whether agreements are extended by
law, how wage setting is coordinated, whether the right to strike is recognised.

Variable labels come from the published codebook rather than from guesswork; a
variable whose definition cannot be read out of the codebook is left out, since
an unlabelled ordinal code is not something a reader can use.
"""
import csv, gzip, io, json, pathlib, re, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SLUG = "OECD_AIAS__ICTWSS"
CSV_URL = "https://webfs.oecd.org/Els-com/ICTWSS-Database/ICTWSS_v2.csv"
CODEBOOK = ("https://www.oecd.org/content/dam/oecd/en/data/datasets/"
            "oecd-aias-ictwss/OECD-AIAS-ICTWSS-v2-Codebook.pdf")

# variables that are genuine percentages rather than ordinal codes
PCT = re.compile(r"density|coverage|rate|share|proportion|percentage", re.I)
COUNTS = re.compile(r"number of|members", re.I)

def get(url, timeout=600):
    req = urllib.request.Request(url, headers={"User-Agent": "ForestAndTheTrees/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r: return r.read()

def definitions(codes):
    import fitz
    raw = get(CODEBOOK)
    doc = fitz.open(stream=raw, filetype="pdf")
    txt = "\n".join(p.get_text() for p in doc)
    out = {}
    for c in codes:
        m = re.search(rf'^\s*{re.escape(c)}\s*[:\-–—]?\s*(.{{10,200}})', txt, re.M)
        if m: out[c] = " ".join(m.group(1).split())
    return out

def main():
    rows = list(csv.DictReader(io.StringIO(get(CSV_URL).decode("utf-8", "replace"))))
    codes = [c for c in rows[0] if c not in ("country", "iso3", "year")]
    defs = definitions(codes)
    print(f"variables in source: {len(codes)}   defined in codebook: {len(defs)}")

    names, records, used = {}, {}, {}
    for r in rows:
        iso = (r.get("iso3") or "").strip()
        if not re.fullmatch(r"[A-Z]{3}", iso): continue
        try: year = str(int(float(r["year"])))
        except (TypeError, ValueError, KeyError): continue
        names.setdefault(iso, (r.get("country") or iso).strip())
        for c in codes:
            if c not in defs: continue
            v = (r.get(c) or "").strip()
            if not v: continue
            try: val = float(v)
            except ValueError: continue
            # ICTWSS marks absent information with negative sentinels: -88 is
            # "not applicable", -99 "no information". They are not measurements.
            if val <= -80: continue
            unit = "PT" if PCT.search(defs[c]) else ("PS" if COUNTS.search(defs[c]) else "SCALE")
            used[c] = unit
            records.setdefault((iso, c, unit), {})[year] = val

    # The codebook gives one line for a family of variables — "Union density
    # rate" covers male, female, public and private alike. The distinction lives
    # in the code suffix, which the codebook documents, so read it from there
    # rather than shipping eight indicators with the same name.
    SUFFIX = [
        ("_male", "men"), ("_female", "women"),
        ("_public", "public sector"), ("_private", "private sector"),
        ("_parttime", "part-time workers"), ("_fulltime", "full-time workers"),
        ("_temp", "temporary contracts"), ("_perm", "permanent contracts"),
        ("_age1524", "aged 15 to 24"), ("_age2554", "aged 25 to 54"),
        ("_age5564", "aged 55 to 64"), ("_ageGE65", "aged 65 and over"),
        ("_age1529", "aged 15 to 29"), ("_age3049", "aged 30 to 49"),
        ("_age5064", "aged 50 to 64"),
    ]
    def label(c):
        base = defs[c][:110]
        bits = [word for suf, word in SUFFIX if suf in c]
        if c.endswith("_s") or "_s_" in c: bits.append("survey-based")
        return f"{base} — {', '.join(bits)}" if bits else base

    measures = [(c, label(c)) for c in codes if c in used]
    seen = {}
    for i, (c, l) in enumerate(measures):
        if l in seen: measures[i] = (c, f"{l} [{c}]")
        seen[l] = c
    unit_lbl = {"PT": "Percentage", "PS": "Number of people",
                "SCALE": "Ordinal code defined by the source"}
    units = sorted({used[c] for c in used})
    area_ids = sorted(names)
    periods = sorted({y for d in records.values() for y in d}, key=int)
    pidx = {y: i for i, y in enumerate(periods)}
    aidx = {a: i for i, a in enumerate(area_ids)}
    midx = {m[0]: i for i, m in enumerate(measures)}
    uidx = {u: i for i, u in enumerate(units)}
    payload = []
    for (a, m, u), s in records.items():
        ys = sorted(s, key=int)
        payload.append({"k": [aidx[a], midx[m], uidx[u]],
                        "t": [pidx[y] for y in ys], "v": [round(s[y], 6) for y in ys]})

    meta = {
      "slug": SLUG, "id": "ICTWSS", "agency": "OECD/AIAS", "version": "2.0",
      "name": "Bargaining institutions (ICTWSS)",
      "description": "",
      "desc_html": ("The institutional half of the OECD/AIAS ICTWSS database, version "
        "2.0: whether the right to organise, to bargain and to strike is recognised, in "
        "the market sector and in government; at what level bargaining happens; whether "
        "agreements are extended by law to firms that never signed them; how wage "
        "setting is coordinated; whether works councils bargain over pay; whether a "
        "tripartite council exists.<br>OECD's statistical service publishes two "
        "variables from this database, union density and bargaining coverage. The rest "
        "is distributed only as a spreadsheet and appears in no SDMX service anywhere."
        "<br>Most of these indicators are ordinal codes rather than quantities: a "
        "higher bargaining level means a different level, not more of something. The "
        "codebook defines each scale."),
      "desc_text": "The institutional half of the OECD/AIAS ICTWSS database: rights of "
        "association, collective bargaining and strike; bargaining level; mandatory "
        "extension; wage coordination; works councils; tripartite councils.",
      "topic": "UNION",
      "dims": [
        {"id": "REF_AREA", "name": "Country", "ids": area_ids,
         "names": [names[a] for a in area_ids]},
        {"id": "MEASURE", "name": "Indicator", "ids": [m[0] for m in measures],
         "names": [m[1] for m in measures],
         "code_defs": {c: defs[c] for c in used}},
        {"id": "UNIT_MEASURE", "name": "Measured as", "ids": units,
         "names": [unit_lbl[u] for u in units]},
      ],
      "time_dim": "TIME_PERIOD", "periods": periods, "statuses": [],
      "area_dim": "REF_AREA", "layout": "single", "hidden_dims": {},
      "n_series": len(payload), "n_obs": sum(len(r["v"]) for r in payload),
      "source_url": "https://www.oecd.org/en/data/datasets/oecdaias-ictwss-database.html",
      "source_notes": [
        f"OECD/AIAS ICTWSS version 2.0. The source carries {len(codes)} variables; the "
        f"{len(measures)} whose definition can be read out of the published codebook are "
        "here. The rest are omitted rather than shown as unlabelled codes.",
        "Absent information is marked in the source with negative sentinels, -88 for not "
        "applicable and -99 for no information. Those are dropped rather than plotted.",
      ],
    }
    d = SITE/"flows"/SLUG; d.mkdir(parents=True, exist_ok=True)
    (d/"all.json.gz").write_bytes(gzip.compress(
        json.dumps(payload, separators=(",", ":")).encode(), 6))
    (d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    print(f'{meta["n_series"]} series, {meta["n_obs"]:,} observations, '
          f'{len(area_ids)} countries, {periods[0]}-{periods[-1]}, {len(measures)} indicators')

main()
