#!/usr/bin/env python3
"""Compare the EPI dataset against a fresh copy of EPI's own release files.

The eleven CSVs behind this dataset were confirmed byte-identical to the current
release, so the inputs are current. This checks the other half: that the values
served match those files, rather than only that the files match.
"""
import csv, gzip, json, pathlib, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FRESH = pathlib.Path("/private/tmp/claude-501/-Users-alexhoffman-Documents/"
                     "5b734f3a-e90a-44b8-ab72-abd591c4d0c9/scratchpad/epi_fresh")

d = ROOT/"site/data/flows/EPI__DF_US_PAY_POWER"
m = json.loads((d/"meta.json").read_text())
recs = json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))
ids = [x["id"] for x in m["dims"]]; D = {x["id"]: x for x in m["dims"]}; P = m["periods"]
mi = ids.index("MEASURE")
bi = next((i for i, x in enumerate(m["dims"]) if x["id"] == "BREAKDOWN"), None)
site = collections.defaultdict(dict)
for r in recs:
    code = D["MEASURE"]["ids"][r["k"][mi]]
    brk = D["BREAKDOWN"]["ids"][r["k"][bi]] if bi is not None else ""
    for t, v in zip(r["t"], r["v"]): site[(code, brk)][P[t]] = v

# The release files are long format: one row per indicator, measure, group and
# year, with the number in a "value" column. Percentages are stored as fractions
# there and scaled by 100 on the way in, so the check has to do the same.
import sys
sys.path.insert(0, str(ROOT/"scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("add_epi", ROOT/"scripts/add_epi.py")
mod = importlib.util.module_from_spec(spec)
mod.__dict__["__name__"] = "audit_only"          # do not let it write anything
try:
    src = (ROOT/"scripts/add_epi.py").read_text()
    ns = {}
    exec(compile(src.split("periods = sorted")[0], "add_epi", "exec"), ns)
    WANT, GRP = ns["WANT"], ns["GRP"]
except Exception as e:
    print("could not read the builder's mapping:", e); raise SystemExit(1)

n = miss = 0
bad = []
for stem, entries in WANT.items():
    f = FRESH/f"{stem}.csv"
    if not f.exists(): print(f"  {stem}: not in the release"); continue
    by = {(e[0]): (e[1], e[3]) for e in entries}     # measure text -> (code, unit)
    for r in csv.DictReader(open(f)):
        if r["value"] in ("", "NA"): continue
        hit = by.get(r["measure"])
        if not hit: continue
        code, unit = hit
        gv = (r.get("group_value") or "").strip()
        brk = GRP.get(gv, (None,))[0] if gv in GRP else "_T"
        if brk is None: continue
        try: v = float(r["value"])
        except ValueError: continue
        if unit in ("PT", "PT_PREM"): v *= 100
        got = site.get((code, brk), {}).get(r["year"])
        if got is None: continue
        n += 1
        if abs(got - v) > max(1e-4, abs(v)*1e-6):
            miss += 1
            if len(bad) < 6: bad.append((code, brk, r["year"], round(v,4), got))
print(f"EPI: compared {n:,} values against the release files, mismatched {miss}")
for b in bad: print("   source vs site:", b)
