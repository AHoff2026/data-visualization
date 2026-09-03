#!/usr/bin/env python3
"""Point every dataset at its own table, not at a search that happened to find it.

Many OECD links were captured during harvesting and carry the search terms and
page offsets of that session ("tm=unions&pg=380"). They resolve, but they are a
record of how the table was found rather than a citation of it. The Data Explorer
takes a canonical deep link built from agency, dataflow and version, so that is
what a reader should get.

Non-OECD sources are left to the curated map in apply_editorial.py, which points
at the primary publisher rather than at whoever re-published them.
"""
import json, pathlib, re, urllib.parse

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"
BASE = "https://data-explorer.oecd.org/vis"

def deep_link(agency, flow_id, version):
    q = {"df[ds]": "dsDisseminateFinalDMZ", "df[id]": flow_id,
         "df[ag]": agency, "df[vs]": version or "1.0"}
    return BASE + "?" + urllib.parse.urlencode(q, safe="@")

changed = cleaned = built = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    agency = meta.get("agency", "") or ""
    if not agency.startswith("OECD."):
        continue                      # non-OECD: curated elsewhere
    url = meta.get("source_url", "") or ""
    want = deep_link(agency, meta.get("id", ""), meta.get("version"))
    if url == want: continue
    if "data-explorer.oecd.org" in url and ("tm=" in url or "pg=" in url or "snb=" in url):
        cleaned += 1
    else:
        built += 1
    meta["source_url"] = want
    mp.write_text(json.dumps(meta, separators=(",", ":")))
    changed += 1
print(f"{changed} OECD source links rewritten as canonical deep links "
      f"({cleaned} had search cruft, {built} were generic or missing)")
