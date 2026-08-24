#!/usr/bin/env python3
"""Where the dropdown sprawl is, and what each option is actually carrying.

Reports every dial with many options, and for each option the share of the
dataset's observations behind it. An option holding a fraction of a per cent is
a candidate for removal; an option holding a third of the data is not.
"""
import json, gzip, pathlib, collections

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"

def load(d, meta):
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for f in sorted((d/"parts").glob("*.json.gz")):
        out += json.loads(gzip.decompress(f.read_bytes()))
    return out

rows = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    recs = load(mp.parent, meta)
    ids = [x["id"] for x in meta["dims"]]
    hidden = set((meta.get("hidden_dims") or {}).keys())
    total = sum(len(r["v"]) for r in recs)
    opts = 0; dials = []
    for i, d in enumerate(meta["dims"]):
        if d["id"] == "REF_AREA" or len(d["ids"]) <= 1: continue
        c = collections.Counter()
        for r in recs: c[r["k"][i]] += len(r["v"])
        share = {d["ids"][j]: c[j]/total*100 if total else 0 for j in range(len(d["ids"]))}
        tail = [k for k, v in share.items() if v < 0.5]
        empty = [k for k, v in share.items() if v == 0]
        opts += len(d["ids"])
        dials.append({"id": d["id"], "name": d["name"], "n": len(d["ids"]),
                      "hidden": d["id"] in hidden, "tail": len(tail), "empty": len(empty),
                      "top": sorted(share.items(), key=lambda kv: -kv[1])[:3],
                      "share": share, "names": dict(zip(d["ids"], d["names"]))})
    rows.append({"slug": meta["slug"], "name": meta["name"], "obs": total,
                 "dials": dials, "opts": opts,
                 "combos": __import__("math").prod([x["n"] for x in dials]) if dials else 0})

rows.sort(key=lambda r: -r["opts"])
print(f'{"dataset":46}{"obs":>12}{"dials":>7}{"options":>9}{"combinations":>14}')
for r in rows[:22]:
    print(f'  {r["name"][:44]:46}{r["obs"]:>12,}{len(r["dials"]):>7}{r["opts"]:>9}{r["combos"]:>14,}')
print("\n\n=== dials with 8 or more options ===")
for r in rows:
    big = [d for d in r["dials"] if d["n"] >= 8 and not d["hidden"]]
    if not big: continue
    print(f'\n{r["name"]}  ({r["obs"]:,} obs)')
    for d in big:
        print(f'   {d["name"]:26} {d["n"]:>3} options  {d["tail"]:>3} under 0.5%  {d["empty"]:>3} empty')
