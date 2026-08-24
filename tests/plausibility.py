#!/usr/bin/env python3
"""Does every series pass a smell test?

Not sampling: every series, against rules that encode what social and labour
statistics cannot do. A share cannot exceed 100. A subgroup cannot exceed the
total it sits inside. A decile ratio cannot be below one. An ordinal scale cannot
leave its own range. A rate does not move sixty points in a year.

Rules are deliberately conservative: a flag is a question, not a verdict.
"""
import json, gzip, pathlib, collections, math, sys

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"
TOTAL_CODES = {"_T", "T", "TOTAL", "_Z"}
# units whose values are bounded shares
PCT = lambda u: u.startswith("PT") or u in {"PC", "PT_POP", "PT_B1GQ"}

def load(d, m):
    if m["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for f in sorted((d/"parts").glob("*.json.gz")):
        out += json.loads(gzip.decompress(f.read_bytes()))
    return out

findings = []
def flag(rule, slug, name, detail, severity="check"):
    findings.append({"rule": rule, "slug": slug, "dataset": name,
                     "detail": detail, "severity": severity})

for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text()); recs = load(mp.parent, meta)
    if not recs: continue
    slug, nm = meta["slug"], meta["name"]
    ids = [x["id"] for x in meta["dims"]]
    D = {x["id"]: x for x in meta["dims"]}
    P = meta["periods"]
    ui = ids.index("UNIT_MEASURE") if "UNIT_MEASURE" in ids else None

    # ---- R1 share out of range, R6 impossible year-on-year move, R5 frozen series
    n_out = n_jump = n_flat = 0
    ex_out = ex_jump = None
    for r in recs:
        unit = D["UNIT_MEASURE"]["ids"][r["k"][ui]] if ui is not None else ""
        vals = r["v"]
        if PCT(unit):
            for t, v in zip(r["t"], vals):
                if v < -0.001 or v > 100.001:
                    n_out += 1
                    if ex_out is None: ex_out = (P[t], v)
            for (t0, v0), (t1, v1) in zip(zip(r["t"], vals), list(zip(r["t"], vals))[1:]):
                try: gap = int(P[t1][:4]) - int(P[t0][:4])
                except ValueError: gap = 1
                if gap == 1 and abs(v1 - v0) > 60:
                    n_jump += 1
                    if ex_jump is None: ex_jump = (P[t0], v0, P[t1], v1)
        if len(vals) >= 12 and len(set(vals)) == 1 and vals[0] != 0:
            n_flat += 1
    if n_out: flag("share outside 0-100", slug, nm,
                   f"{n_out} values, e.g. {ex_out[0]}: {ex_out[1]:.2f}", "high")
    if n_jump: flag("moves >60 points in one year", slug, nm,
                    f"{n_jump} steps, e.g. {ex_jump[0]}:{ex_jump[1]:.1f} -> {ex_jump[2]}:{ex_jump[3]:.1f}")
    if n_flat: flag("identical value for 12+ periods", slug, nm, f"{n_flat} series")

    # ---- R2 a breakdown category exceeding its own total
    for i, d in enumerate(meta["dims"]):
        if d["id"] in ("REF_AREA", "UNIT_MEASURE", "MEASURE", "TIME_PERIOD"): continue
        tot = next((c for c in d["ids"] if c in TOTAL_CODES), None)
        if tot is None or len(d["ids"]) < 3: continue
        ti = d["ids"].index(tot)
        buckets = collections.defaultdict(dict)
        for r in recs:
            unit = D["UNIT_MEASURE"]["ids"][r["k"][ui]] if ui is not None else ""
            if not PCT(unit): continue
            key = tuple(v for j, v in enumerate(r["k"]) if j != i)
            for t, v in zip(r["t"], r["v"]): buckets[(key, t)][r["k"][i]] = v
        bad = 0; ex = None
        for (key, t), mm in buckets.items():
            if ti not in mm: continue
            T = mm[ti]
            if T <= 0: continue
            for j, v in mm.items():
                if j != ti and v > T * 1.02 + 0.5:
                    bad += 1
                    if ex is None: ex = (d["names"][j], v, d["names"][ti], T, P[t])
        if bad:
            flag("category exceeds its own total", slug, nm,
                 f'{d["name"]}: {bad} cases, e.g. "{ex[0]}" {ex[1]:.1f} > "{ex[2]}" {ex[3]:.1f} in {ex[4]}',
                 "high")

    # ---- R7 a ratio below one
    if ui is not None:
        for r in recs:
            unit = D["UNIT_MEASURE"]["ids"][r["k"][ui]]
            if unit in ("RATIO", "FCTR") and any(v < 1 for v in r["v"]):
                flag("decile ratio below 1", slug, nm,
                     f"min {min(r['v']):.3f}", "high"); break

print(f"{len(findings)} flags\n")
by = collections.Counter(f["rule"] for f in findings)
for k, v in by.most_common(): print(f"  {v:>4}  {k}")
print()
for f in sorted(findings, key=lambda f: (f["severity"] != "high", f["dataset"])):
    mark = "!!" if f["severity"] == "high" else "  "
    print(f'{mark} {f["dataset"][:38]:40} {f["rule"][:32]:34} {f["detail"][:92]}')
json.dump(findings, open("/tmp/plausibility.json", "w"), indent=1)

# ---- a default view that cannot say anything -----------------------------
# A reference group plotted against itself is constant at 100 by construction.
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    b = (meta.get("default_bundle") or {}).get("picks") or {}
    unit = b.get("UNIT_MEASURE", "")
    for k, v in b.items():
        if k != "UNIT_MEASURE" and v and unit.endswith(v):
            print(f'!! {meta["name"][:38]:40} default view is self-referential: '
                  f'{k}={v} against unit {unit}')
