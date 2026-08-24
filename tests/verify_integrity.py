#!/usr/bin/env python3
"""Check that everything the site references actually exists.

Consolidation removes datasets, and a home-page card or a saved text override
can quietly outlive the thing it points at.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site"
cat = json.loads((SITE/"data/catalog.json").read_text())
slugs = {f["slug"] for f in cat["flows"]}
fails = []

# every catalog entry has a payload on disk, and vice versa
for s in slugs:
    if not (SITE/"data/flows"/s/"meta.json").exists():
        fails.append(f"catalog lists {s} but there is no payload")
# Retired datasets are deliberately on disk and off the rail: the data is kept so
# the decision can be reversed, but it is not offered to a reader.
RETIRED = set()
_ed = pathlib.Path(__file__).resolve().parent.parent/"scripts/apply_editorial.py"
if _ed.exists():
    import ast
    for node in ast.walk(ast.parse(_ed.read_text())):
        if (isinstance(node, ast.Assign) and node.targets
                and getattr(node.targets[0], "id", "") == "RETIRED"):
            RETIRED = set(ast.literal_eval(node.value))
for d in (SITE/"data/flows").iterdir():
    if d.is_dir() and d.name not in slugs and d.name not in RETIRED:
        fails.append(f"payload {d.name} is on disk but not in the catalog")
print(f"retired but kept on disk: {len(RETIRED)}")

# home-page cards
for m in re.finditer(r'slug: "([^"]+)"', (SITE/"js/featured.js").read_text()):
    if m.group(1) not in slugs:
        fails.append(f"home page features {m.group(1)}, which no longer exists")

# featured ordering and per-flow flags
for s in cat.get("featured_order", []):
    if s not in slugs: fails.append(f"featured_order names {s}, which no longer exists")

# saved text overrides
ov = SITE/"data/overrides.json"
if ov.exists():
    for k in json.loads(ov.read_text()):
        if k.startswith("/d/") and k[3:] not in slugs:
            fails.append(f"text override for {k}, whose dataset no longer exists")
        if k.startswith("/featured/") and k[len("/featured/"):] not in slugs:
            fails.append(f"text override for {k}, whose dataset no longer exists")

# each flow's meta agrees with the catalog
for f in cat["flows"]:
    m = json.loads((SITE/"data/flows"/f["slug"]/"meta.json").read_text())
    if m["name"] != f["name"]:
        fails.append(f'{f["slug"]}: catalog name "{f["name"]}" != meta name "{m["name"]}"')
    if m.get("n_obs") != f.get("n_obs"):
        fails.append(f'{f["slug"]}: observation counts disagree')

# a dial with two identically named options cannot be used
for f in cat["flows"]:
    m = json.loads((SITE/"data/flows"/f["slug"]/"meta.json").read_text())
    for d in m["dims"]:
        seen = {}
        for cid, cnm in zip(d["ids"], d["names"]):
            if cnm in seen:
                fails.append(f'{f["slug"]}: {d["name"]} offers "{cnm}" twice '
                             f'({seen[cnm]} and {cid})')
            seen[cnm] = cid

print(f"datasets: {len(slugs)}")
if fails:
    print(f"INTEGRITY FAILURES: {len(fails)}")
    for x in fails: print("   ", x)
    sys.exit(1)
print("ALL INTERNAL REFERENCES RESOLVE")
