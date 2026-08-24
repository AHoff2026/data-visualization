#!/usr/bin/env python3
"""Classify every observation by where its number came from.

Three classes. Published: the source publishes this number and it is reproduced
unchanged. Derived: the number is arithmetic performed here on published values --
a ratio, a share, a per-capita normalisation, a sum of categories. Relabelled:
the number is the source's but the words around it are editorial.

A reader has to be able to tell which is which, so this is the report that says so.
"""
import json, gzip, pathlib, collections

SITE = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"

# measures computed here rather than published, by flow slug
DERIVED_MEASURES = {
  "OWID__LABOR_SHARE": {
     "LS_GDP","LS_FC","LS_ADJ_HRS_GDP","LS_ADJ_HRS_FC","LS_ADJ_PER_FC","CAP_FC",
     "TAX_GDP","SELF_HRS","LS_WID","LS_Q_ALL","LS_Q_EMP","PROP_Q"},
  "ESTAT__DF_DEPRIVATION": {"ENDS_MEET"},
}
def load(d, meta):
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for f in sorted((d/"parts").glob("*.json.gz")):
        out += json.loads(gzip.decompress(f.read_bytes()))
    return out

tot = collections.Counter(); rows = []
for mp in sorted(SITE.glob("*/meta.json")):
    meta = json.loads(mp.read_text()); slug = meta["slug"]
    recs = load(mp.parent, meta)
    ids = [x["id"] for x in meta["dims"]]
    dsets = meta.get("derived_units", {}) or {}
    ui = ids.index("UNIT_MEASURE") if "UNIT_MEASURE" in ids else None
    mi = next((i for i,x in enumerate(meta["dims"])
               if x["id"] in ("MEASURE","ITEM","INDICATOR")), None)
    dm = DERIVED_MEASURES.get(slug, set())
    n_pub = n_der = 0
    for r in recs:
        k = len(r["v"])
        is_d = False
        if ui is not None and meta["dims"][ui]["ids"][r["k"][ui]] in dsets: is_d = True
        if mi is not None and meta["dims"][mi]["ids"][r["k"][mi]] in dm: is_d = True
        if is_d: n_der += k
        else: n_pub += k
    deleted = sum(1 for s in meta.get("source_notes", [])
                  if "removed" in s.lower() or "dropped" in s.lower())
    tot["published"] += n_pub; tot["derived"] += n_der
    if n_der or deleted:
        rows.append((slug, meta["name"], n_pub, n_der, deleted))

print(f'{"":52}{"published":>13}{"derived here":>14}')
for slug, name, p, d, dl in sorted(rows, key=lambda r: -r[3]):
    flag = "  [has deletion note]" if dl else ""
    print(f'  {name[:50]:52}{p:>13,}{d:>14,}{flag}')
g = tot["published"] + tot["derived"]
print(f'\n  {"TOTAL":50}{tot["published"]:>13,}{tot["derived"]:>14,}')
print(f'  derived share of all observations: {tot["derived"]/g*100:.2f}%')
