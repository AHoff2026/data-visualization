#!/usr/bin/env python3
"""Recompute every derived value from its published components and compare.

Roughly one value in three hundred on this site is arithmetic performed here
rather than a figure the source published. Those are the ones that can be wrong
in ways no source check would catch, because there is nothing upstream to
compare them against. So they are recomputed from scratch and checked against
what is being served.
"""
import json, gzip, pathlib, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

def load(slug):
    d = FLOWS/slug
    m = json.loads((d/"meta.json").read_text())
    if m["layout"] == "single":
        f = d/"all.json.gz"
        r = json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    else:
        r = [x for f in sorted((d/"parts").glob("*.json.gz"))
             for x in json.loads(gzip.decompress(f.read_bytes()))]
    return m, r

bad = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    du = meta.get("derived_units") or {}
    if not du: continue
    m, recs = load(meta["slug"])
    ids = [x["id"] for x in m["dims"]]
    D = {x["id"]: x for x in m["dims"]}
    P = m["periods"]
    ui = ids.index("UNIT_MEASURE")
    for code, spec in du.items():
        if code not in D["UNIT_MEASURE"]["ids"]: continue
        over = spec.get("over"); total = spec.get("total_code")
        if not over or over not in ids: 
            print(f"  {m['name'][:40]:42} {code}: spec names no dimension"); continue
        oi = ids.index(over)
        want = D["UNIT_MEASURE"]["ids"].index(code)
        # the base unit is whichever other unit the dataset carries
        bases = [j for j, c in enumerate(D["UNIT_MEASURE"]["ids"]) if j != want]
        vals = collections.defaultdict(dict)
        for r in recs:
            k = tuple(v for i, v in enumerate(r["k"]) if i not in (ui, oi))
            u = r["k"][ui]; o = D[over]["ids"][r["k"][oi]]
            for t, v in zip(r["t"], r["v"]): vals[(k, t)][(u, o)] = v
        checked = wrong = 0; ex = []
        tcodes = [c.strip() for c in str(total).split("+")] if total else []
        for (k, t), mm in vals.items():
            for (u, o), v in list(mm.items()):
                if u != want: continue
                base = next((mm.get((b, o)) for b in bases if (b, o) in mm), None)
                den = 0.0; ok = True
                for tc in tcodes:
                    d2 = next((mm.get((b, tc)) for b in bases if (b, tc) in mm), None)
                    if d2 is None: ok = False; break
                    den += d2
                if not ok or base is None or den <= 0: continue
                checked += 1
                exp = base/den*100
                if abs(exp - v) > max(0.01, abs(exp)*0.001):
                    wrong += 1
                    if len(ex) < 3: ex.append((P[t], round(exp,4), v))
        note = f"  {m['name'][:40]:42} {code}: recomputed {checked:>7,}  disagreeing {wrong:>5}"
        if wrong: note += "   e.g. " + "; ".join(f"{p} expected {e} served {s}" for p,e,s in ex)
        print(note)
        bad += wrong
print(f"\n{bad} derived values disagree with a fresh recomputation")
