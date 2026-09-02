#!/usr/bin/env python3
"""Say what a regional aggregate is, on every dataset that offers one.

OECD, EU27, G7 and the euro-area rows are not measurements of a region. They are
built from whichever member countries reported that particular cell in that
particular year, so their composition changes from cell to cell and from year to
year. Two consequences a reader will otherwise meet as nonsense: a component can
exceed the total it belongs to, because the two are averaged over different sets
of countries; and a count for a region can be absurdly small, because only a
handful of members reported it.

Idempotent, and safe to re-run after any rebuild.
"""
import json, pathlib, re

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"
AGG = re.compile(r"^(OECD|OECD_REP|EU\d*|EU\d+_\d+|EU\d+OECD|EUOECD|EA\d*|G7|G20|WLD)$")
NOTE = ("Regional rows such as OECD, EU27 and G7 are compiled from whichever member "
        "countries reported that particular figure in that particular year, so what "
        "they cover changes between one selection and the next. Two things follow. A "
        "breakdown can exceed the total it belongs to, because the two are built from "
        "different sets of countries. And a count for a region can come out far too "
        "small, because only some members reported it. Compare countries directly where "
        "the question allows it; read the regional rows as a rough centre of gravity "
        "rather than as a measurement of the region.")

added = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    area = next((d for d in meta["dims"] if d["id"] == "REF_AREA"), None)
    if not area: continue
    aggs = [c for c in area["ids"] if AGG.match(c)]
    if not aggs: continue
    notes = meta.get("source_notes") or []
    if any("rough centre of gravity" in n for n in notes): continue
    notes.append(NOTE)
    meta["source_notes"] = notes
    # mark them so the interface can treat them differently later
    area["aggregates"] = sorted(area["ids"].index(c) for c in aggs)
    mp.write_text(json.dumps(meta, separators=(",", ":")))
    added += 1
print(f"aggregate caveat added to {added} datasets")
