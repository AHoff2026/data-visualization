#!/usr/bin/env python3
"""Check every derived share against the published counts it came from."""
import json, gzip, pathlib, sys
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

def load(mp, meta):
    d = mp.parent
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for info in (meta.get("parts") or {}).values():
        f = d/"parts"/info["file"]
        if f.exists(): out.extend(json.loads(gzip.decompress(f.read_bytes())))
    return out

fail = 0; checked = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    du = meta.get("derived_units")
    if not du: continue
    idx = {d["id"]: i for i, d in enumerate(meta["dims"])}
    ui = idx["UNIT_MEASURE"]
    recs = load(mp, meta)
    for code, info in du.items():
        di = idx[info["over"]]
        dim = meta["dims"][di]
        new_ui = meta["dims"][ui]["ids"].index(code)
        tcode = info["total_code"]
        parts = [dim["ids"].index(c) for c in tcode.split("+") if c in dim["ids"]]
        counts = defaultdict(dict); totals = defaultdict(lambda: defaultdict(float))
        for r in recs:
            if r["k"][ui] == new_ui: continue
            key = tuple(v for i, v in enumerate(r["k"]) if i != di)
            counts[(key, r["k"][di])] = dict(zip(r["t"], r["v"]))
            if r["k"][di] in parts:
                for ti, v in zip(r["t"], r["v"]): totals[key][ti] += v
        bad = 0; n = 0
        for r in recs:
            if r["k"][ui] != new_ui: continue
            key = tuple(v for i, v in enumerate(r["k"]) if i != di)
            key = tuple(new_ui if i == ui - (1 if ui > di else 0) else v
                        for i, v in enumerate(key))  # unit differs; rebuild below
            # rebuild the source key with the original unit
            src = list(r["k"]); 
            for orig_ui in range(len(meta["dims"][ui]["ids"])):
                if orig_ui == new_ui: continue
                src[ui] = orig_ui
                ck = tuple(v for i, v in enumerate(src) if i != di)
                num = counts.get((ck, r["k"][di]))
                den = totals.get(ck)
                if num and den: break
            else:
                continue
            if not num or not den: continue
            for ti, v in zip(r["t"], r["v"]):
                if ti not in num or ti not in den or den[ti] == 0: continue
                want = num[ti] / den[ti] * 100
                n += 1
                if abs(want - v) > 0.01: bad += 1
        checked += n; fail += bad
        status = "ok  " if bad == 0 else "FAIL"
        print(f'{status} {meta["slug"]:44} {code:10} {n:7} values checked, {bad} wrong')

print(f"\n{'='*68}\nDERIVED VALUES CHECKED: {checked:,}   WRONG: {fail}")
sys.exit(1 if fail else 0)
