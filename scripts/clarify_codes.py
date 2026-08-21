#!/usr/bin/env python3
"""Give OECD's residual categories names a reader can act on, and mark them so
the interface can sort them below the substantive choices.

These carry real observations — "Employees and unknown" is a sixth of the
permanency table, because some countries report those together — so they are
renamed, never dropped.
"""
import json, pathlib, re

ROOT = pathlib.Path.home()/"Documents/data-visualization"
RENAME = {
    "_U":         "Not reported",
    "_X":         "Not classified elsewhere",
    "_TX_U":      "Total (excluding not reported)",
    "ICSE93_1_U": "Employees, including unclassified",
    "ICSE93_1_TEMP": "Employees on a temporary contract",
}
# by display text, for codes that vary
TEXT = [
    (r"^No data/unknown$",              "Not reported"),
    (r"^Unspecified$",                  "Not classified elsewhere"),
    (r"^Unknown$",                      "Not reported"),
    (r"^Total \(excluding unknown\)$",  "Total (excluding not reported)"),
    (r"\band unknown\b",                "and unclassified"),
]
RESIDUAL = re.compile(r"not reported|not classified|unclassified|unknown|unspecified", re.I)

n_ren = n_mark = 0
for mp in sorted((ROOT/"site/data/flows").glob("*/meta.json")):
    m = json.loads(mp.read_text()); ch = False
    for d in m["dims"]:
        residual = []
        for j, (cid, cnm) in enumerate(zip(d["ids"], d["names"])):
            new = RENAME.get(cid)
            if not new:
                new = cnm
                for pat, rep in TEXT: new = re.sub(pat, rep, new)
            if new != cnm:
                d["names"][j] = new; ch = True; n_ren += 1
            if RESIDUAL.search(d["names"][j]) and not d["names"][j].lower().startswith("total"):
                residual.append(j)
        if residual:
            d["residual"] = residual; ch = True; n_mark += len(residual)
    if ch: mp.write_text(json.dumps(m, separators=(",", ":")))
print(f"codes renamed: {n_ren}   marked residual: {n_mark}")
