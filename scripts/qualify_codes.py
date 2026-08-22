#!/usr/bin/env python3
"""Disambiguate dial options whose names repeat.

OECD's programme codes are unique only inside their branch: "Pension" appears
under old age, incapacity and survivors alike. Listed flat, a reader cannot tell
which one they are picking. This walks the published codelist hierarchy and
prefixes the parent where a name would otherwise repeat.
"""
import json, pathlib, re

ROOT = pathlib.Path.home()/"Documents/data-visualization"
STRUCT, FLOWS = ROOT/"meta/struct", ROOT/"site/data/flows"

def urn_tail(urn):
    if not urn: return None
    t = urn.split("=")[-1]
    m = re.match(r'([^:]+):([^(]+)\(', t)
    return f"{m.group(1)}:{m.group(2)}" if m else None

fixed = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    slug = mp.parent.name
    sp = STRUCT/f"{slug}.json"
    if not sp.exists(): continue
    meta = json.loads(mp.read_text())
    d = json.loads(sp.read_text())["data"]

    codelists = {}
    for cl in d.get("codelists", []):
        key = f'{cl.get("agencyID")}:{cl["id"]}'
        codelists[key] = {c["id"]: c for c in cl.get("codes", [])}
    dim_cl = {}
    for dim in d["dataStructures"][0]["dataStructureComponents"]["dimensionList"]["dimensions"]:
        k = urn_tail(dim.get("localRepresentation", {}).get("enumeration"))
        if k: dim_cl[dim["id"]] = k

    changed = False
    for dm in meta["dims"]:
        dm["names"] = [re.sub(r"\s*\[[A-Z0-9_]+\]$", "", n) for n in dm["names"]]
        counts = {}
        for n in dm["names"]: counts[n] = counts.get(n, 0) + 1
        dupes = {n for n, c in counts.items() if c > 1}
        if not dupes: continue
        codes = codelists.get(dim_cl.get(dm["id"]), {})
        for j, (cid, cnm) in enumerate(zip(dm["ids"], dm["names"])):
            if cnm not in dupes: continue
            node = codes.get(cid) or {}
            parent_id = (node.get("parent") or "").split(".")[-1]
            parent = codes.get(parent_id) or {}
            pname = parent.get("name")
            # Many OECD codelists carry no parent links but encode the hierarchy
            # in the code itself: TP111 sits under TP11 ("Old age"), which sits
            # under TP1. Walk the prefixes until a real parent turns up.
            # SOCX programme codes are TP<area><kind><item>: TP122 is old age
            # (area 1), in kind (kind 2), other benefits. Its branch heading is
            # TP11, which is not a prefix of it.
            if not pname:
                m2 = re.fullmatch(r"TP(\d)(\d)(\d)", cid)
                if m2:
                    head = codes.get(f"TP{m2.group(1)}1")
                    if head and head.get("name") and head["name"] != cnm:
                        pname = head["name"]
            if not pname:
                stem = cid
                while len(stem) > 1:
                    stem = stem[:-1]
                    cand = codes.get(stem)
                    if cand and cand.get("name") and cand["name"] != cnm:
                        pname = cand["name"]; break
            if pname and pname != cnm:
                dm["names"][j] = f"{pname} · {cnm}"
                changed = True; fixed += 1
        # anything still duplicated gets its code, so the two are at least distinct
        counts = {}
        for n in dm["names"]: counts[n] = counts.get(n, 0) + 1
        for j, n in enumerate(dm["names"]):
            if counts[n] > 1:
                dm["names"][j] = f"{n} [{dm['ids'][j]}]"
                changed = True; fixed += 1
    if changed:
        mp.write_text(json.dumps(meta, separators=(",", ":")))
print(f"ambiguous option labels qualified: {fixed}")
