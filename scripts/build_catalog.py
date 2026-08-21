#!/usr/bin/env python3
"""Turn harvested SDMX structures into a single catalog: topic tree, dataflows,
dimensions, codelists (with hierarchy), and the default view from each Safari tab."""
import json, pathlib, re, urllib.parse as up
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
STRUCT = ROOT/"meta/struct"
manifest = json.loads((ROOT/"meta/manifest.json").read_text())
DEFAULT_COUNTRIES = ["DEU","FRA","GBR","USA","SWE","DNK","NOR","FIN","AUT","ESP","ITA","CAN","NLD"]

def slug(r): return f'{r["agency"]}__{r["flow"]}'

def urn_id(urn):
    """urn:...Category=OECD:OECDCS1(5.4).JOB  -> ('OECDCS1','JOB')"""
    if not urn: return None, None
    tail = urn.split("=")[-1]
    m = re.match(r'([^:]+):([^(]+)\(([^)]+)\)(?:\.(.+))?$', tail)
    if not m: return None, None
    return m.group(2), m.group(4)

topic_tree = None
flows = []
codelists = {}          # global pool, deduped by id+agency
missing_topic = []

for r in manifest:
    p = STRUCT/f"{slug(r)}.json"
    if not p.exists(): continue
    d = json.loads(p.read_text())["data"]
    df = d["dataflows"][0]

    if topic_tree is None:
        for cs in d.get("categorySchemes", []):
            if cs.get("id") == "OECDCS1":
                topic_tree = cs
                break

    # categorisation -> topic path
    topic_code = None
    for c in d.get("categorisations", []):
        if r["dataflow_id"] in (c.get("source") or ""):
            _, topic_code = urn_id(c.get("target"))
            if topic_code: break
    if not topic_code: missing_topic.append(slug(r))

    ds = d["dataStructures"][0]
    comp = ds["dataStructureComponents"]
    dims = []
    for dim in comp["dimensionList"]["dimensions"]:
        cl_urn = dim.get("localRepresentation", {}).get("enumeration")
        ag, _ = urn_id(cl_urn)
        cl_ag = (cl_urn.split("=")[-1].split(":")[0] if cl_urn else None)
        cl_id = ag
        dims.append({
            "id": dim["id"],
            "name": dim.get("name") or dim["id"],
            "position": dim.get("position"),
            "codelist": f"{cl_ag}:{cl_id}" if cl_id else None,
        })
    time_dims = comp["dimensionList"].get("timeDimensions", [])
    attrs = [{"id": a["id"], "name": a.get("name") or a["id"]}
             for a in comp.get("attributeList", {}).get("attributes", [])]

    for cl in d.get("codelists", []):
        key = f'{cl.get("agencyID")}:{cl["id"]}'
        if key in codelists: continue
        codes = []
        for c in cl.get("codes", []):
            e = {"id": c["id"], "name": c.get("name") or c["id"]}
            par = c.get("parent")
            if par: e["parent"] = par
            codes.append(e)
        codelists[key] = {"id": cl["id"], "agency": cl.get("agencyID"),
                          "name": cl.get("name"), "codes": codes}

    # content constraint: which codes actually carry data
    used = {}
    for cc in d.get("contentConstraints", []):
        for cr in cc.get("cubeRegions", []):
            for kv in cr.get("keyValues", []):
                used.setdefault(kv["id"], set()).update(kv.get("values", []))
    used = {k: sorted(v) for k, v in used.items()}

    flows.append({
        "slug": slug(r),
        "id": df["id"], "agency": r["agency"], "version": r["version"],
        "name": df.get("name") or df["id"],
        "description": df.get("description") or "",
        "topic": topic_code,
        "dsd": r["dsd"],
        "dimensions": dims,
        "time_dimension": time_dims[0]["id"] if time_dims else "TIME_PERIOD",
        "attributes": attrs,
        "used_codes": used,
        "source_url": r["url"],
        "tab_default_key": r["default_key"],
        "tab_period": r["period"],
    })

out = {
    "generated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
    "default_countries": DEFAULT_COUNTRIES,
    "topic_tree": topic_tree,
    "flows": flows,
    "codelists": codelists,
}
(ROOT/"meta/catalog.json").write_text(json.dumps(out, indent=1))
print(f"flows        : {len(flows)}")
print(f"codelists    : {len(codelists)}")
print(f"missing topic: {missing_topic}")
by = defaultdict(list)
for f in flows: by[f["topic"]].append(f["name"])
print("\nTOPICS USED:")
for t, names in sorted(by.items(), key=lambda x: -len(x[1])):
    print(f"  {t:6} {len(names):2}  e.g. {names[0][:60]}")
