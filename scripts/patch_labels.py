#!/usr/bin/env python3
"""Resolve human labels for dimension names and code names from the harvested
SDMX structures, and patch them into each flow's meta.json."""
import json, pathlib, re

ROOT = pathlib.Path.home()/"Documents/data-visualization"
STRUCT, FLOWS = ROOT/"meta/struct", ROOT/"site/data/flows"

def urn_tail(urn):
    """urn:...Concept=AG:CS_X(1.0).REF_AREA -> ('AG','CS_X','REF_AREA')"""
    if not urn: return (None, None, None)
    t = urn.split("=")[-1]
    m = re.match(r'([^:]+):([^(]+)\(([^)]+)\)(?:\.(.+))?$', t)
    return (m.group(1), m.group(2), m.group(4)) if m else (None, None, None)

report = {"flows": 0, "dim_names": 0, "code_names": 0, "unresolved": []}

for mp in sorted(FLOWS.glob("*/meta.json")):
    slug = mp.parent.name
    sp = STRUCT/f"{slug}.json"
    if not sp.exists():
        report["unresolved"].append(f"{slug}: no struct"); continue
    d = json.loads(sp.read_text())["data"]
    meta = json.loads(mp.read_text())

    # concept id -> label
    concept = {}
    for cs in d.get("conceptSchemes", []):
        for c in cs.get("concepts", []):
            concept[c["id"]] = c.get("name") or c["id"]

    # codelist key -> {code: label}
    codemap = {}
    for cl in d.get("codelists", []):
        key = f'{cl.get("agencyID")}:{cl["id"]}'
        codemap[key] = {c["id"]: (c.get("name") or c["id"]) for c in cl.get("codes", [])}

    # dimension -> its codelist key, from the DSD
    dim_cl = {}
    comp = d["dataStructures"][0]["dataStructureComponents"]
    for dim in comp["dimensionList"]["dimensions"]:
        ag, cid, _ = urn_tail(dim.get("localRepresentation", {}).get("enumeration"))
        if ag and cid: dim_cl[dim["id"]] = f"{ag}:{cid}"

    changed = False
    for dm in meta["dims"]:
        lbl = concept.get(dm["id"])
        if lbl and lbl != dm.get("name"):
            dm["name"] = lbl; report["dim_names"] += 1; changed = True
        cm = codemap.get(dim_cl.get(dm["id"]), {})
        if cm:
            new = [cm.get(c, dm["names"][i] if i < len(dm["names"]) else c)
                   for i, c in enumerate(dm["ids"])]
            if new != dm["names"]:
                report["code_names"] += sum(1 for a, b in zip(new, dm["names"]) if a != b)
                dm["names"] = new; changed = True
        else:
            miss = [c for c in dm["ids"] if c not in cm]
            if miss: report["unresolved"].append(f'{slug}.{dm["id"]}: no codelist ({len(miss)} codes)')

    if changed:
        mp.write_text(json.dumps(meta, separators=(",", ":")))
        report["flows"] += 1

print(json.dumps({k: v for k, v in report.items() if k != "unresolved"}, indent=1))
print(f'unresolved: {len(report["unresolved"])}')
for u in report["unresolved"][:15]: print("  ", u)
