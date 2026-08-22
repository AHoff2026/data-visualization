#!/usr/bin/env python3
"""Check that every dataset still exists at OECD under the id we cite.

The site names an agency, dataflow and version under each chart. If OECD retires
or renumbers one, that citation becomes false.
"""
import json, pathlib, urllib.request, urllib.error, sys, time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path.home()/"Documents/data-visualization"
BASE = "https://sdmx.oecd.org/public/rest/dataflow"
cat = json.loads((ROOT/"site/data/catalog.json").read_text())

def check(f):
    m = json.loads((ROOT/"site/data/flows"/f["slug"]/"meta.json").read_text())
    url = f'{BASE}/{m["agency"]}/{m["id"]}/{m["version"]}'
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.sdmx.structure+json;version=1.0",
        "User-Agent": "ForestAndTheTrees/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return (f["name"], m["agency"], m["id"], r.status, "")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 2: time.sleep(4 * (attempt + 1)); continue
            return (f["name"], m["agency"], m["id"], e.code, "")
        except Exception as e:
            if attempt < 2: time.sleep(3); continue
            return (f["name"], m["agency"], m["id"], 0, f"{type(e).__name__}")
    return (f["name"], m["agency"], m["id"], 0, "unreachable")

with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(check, cat["flows"]))
bad = [r for r in res if r[3] != 200]
print(f"datasets checked: {len(res)}   citations that no longer resolve: {len(bad)}")
for n, ag, i, code, err in bad:
    print(f"   HTTP {code} {err:14} {ag} {i}   {n[:40]}")
sys.exit(1 if bad else 0)
