#!/usr/bin/env python3
"""Add share-of-total units to datasets that publish only counts.

Cross-country comparison of absolute counts mostly measures country size. Where
a dataset carries its own total along some dimension, the share is exact
arithmetic on published figures — no external data, no estimation. Derived
series are tagged so the site can label them as computed rather than published.
"""
import json, gzip, pathlib, sys
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

# flow -> (dimension to normalise over, total codes to try, new unit code, label)
PLAN = {
  "OECD.ELS.SAE__DF_DUR_D": ("DURATION", ["_T", "TOTD"], "PT_UNE_D",
      "Percentage of unemployed (derived)"),
  # no published total: full-time and part-time are mutually exclusive, so the
  # denominator is their sum
  "OECD.ELS.SAE__DF_FTPT_COMMON": ("WORK_TIME_ARNGMNT", ["SUM:FT,PT"], "PT_EMP_D",
      "Percentage of employment (derived)"),
  "OECD.ELS.SAE__DF_TEMP_D": ("MEASURE", ["EMP"], "PT_EMP_D",
      "Percentage of employment (derived)"),
  # activity codes overlap (BTF = BTE + F, C is inside BTE); A + BTF + GTU + _X
  # is the non-overlapping partition of total employment
  "OECD.SDD.TPS__DF_IALFS_EMP_ISIC4_Q": ("ACTIVITY", ["SUM:A,BTF,GTU|_X"], "PT_EMP_D",
      "Percentage of employment (derived)"),
}

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

def save(mp, meta, recs):
    d = mp.parent
    if meta["layout"] == "single":
        (d/"all.json.gz").write_bytes(gzip.compress(
            json.dumps(recs, separators=(",", ":")).encode(), 6))
    else:
        ai = next(i for i, x in enumerate(meta["dims"]) if x["id"] == meta["area_dim"])
        codes = meta["dims"][ai]["ids"]
        by = defaultdict(list)
        for r in recs: by[codes[r["k"][ai]]].append(r)
        parts = {}
        for code, rs in by.items():
            fn = (meta.get("parts") or {}).get(code, {}).get("file") or (
                "".join(c if c.isalnum() or c in "._-" else "_" for c in code) + ".json.gz")
            blob = gzip.compress(json.dumps(rs, separators=(",", ":")).encode(), 6)
            (d/"parts"/fn).write_bytes(blob)
            parts[code] = {"file": fn, "n": len(rs), "bytes": len(blob)}
        meta["parts"] = parts
    mp.write_text(json.dumps(meta, separators=(",", ":")))

def run(slug):
    mp = FLOWS/slug/"meta.json"
    if not mp.exists(): return f"{slug}: missing"
    dim_id, totals, new_code, new_label = PLAN[slug]
    meta = json.loads(mp.read_text())
    idx = {d["id"]: i for i, d in enumerate(meta["dims"])}
    if dim_id not in idx: return f"{slug}: no {dim_id} dimension"
    ui = idx.get("UNIT_MEASURE")
    if ui is None: return f"{slug}: no UNIT_MEASURE"
    di = idx[dim_id]
    dim = meta["dims"][di]
    sum_codes = None
    req_set = None
    tot = next((dim["ids"].index(t) for t in totals if t in dim["ids"]), None)
    if tot is None:
        spec = next((t for t in totals if t.startswith("SUM:")), None)
        if spec:
            body = spec[4:]
            req_part, _, opt_part = body.partition("|")
            required = [dim["ids"].index(c) for c in req_part.split(",") if c in dim["ids"]]
            optional = [dim["ids"].index(c) for c in opt_part.split(",") if c in dim["ids"]]
            sum_codes = required + optional
            req_set = set(required)
            if not sum_codes: return f"{slug}: none of {spec} present"
        else:
            return f"{slug}: no total code among {totals}"

    if new_code in meta["dims"][ui]["ids"]:
        return f"{slug}: already derived"
    recs = load(mp, meta)
    if not recs: return f"{slug}: no records"

    # add the new unit code
    unit = meta["dims"][ui]
    unit["ids"].append(new_code); unit["names"].append(new_label)
    unit.setdefault("derived", []).append(new_code)
    new_ui = len(unit["ids"]) - 1

    # index the totals by every dimension except the one being normalised
    def key_ex(r, exclude):
        return tuple(v for i, v in enumerate(r["k"]) if i != exclude)
    totmap = {}
    if sum_codes is not None:
        # Only sum a denominator when every component is present at that period.
        # A partial sum understates the total and produces shares above 100.
        acc = defaultdict(lambda: defaultdict(float))
        seen = defaultdict(lambda: defaultdict(set))
        for r in recs:
            if r["k"][di] not in sum_codes: continue
            k = key_ex(r, di)
            for ti, v in zip(r["t"], r["v"]):
                acc[k][ti] += v
                seen[k][ti].add(r["k"][di])
        need = req_set or set(sum_codes)
        totmap = {k: {ti: v for ti, v in d2.items() if seen[k][ti] >= need}
                  for k, d2 in acc.items()}
        is_total = lambda rec: rec["k"][di] in sum_codes and len(sum_codes) == 1
    else:
        for r in recs:
            if r["k"][di] != tot: continue
            totmap[key_ex(r, di)] = dict(zip(r["t"], r["v"]))
        is_total = lambda rec: rec["k"][di] == tot

    made = 0
    dropped = [0]
    out = list(recs)
    for r in recs:
        if is_total(r): continue
        base = totmap.get(key_ex(r, di))
        if not base: continue
        t2, v2 = [], []
        for ti, v in zip(r["t"], r["v"]):
            b = base.get(ti)
            if b in (None, 0): continue
            share = v / b * 100
            # the source is internally inconsistent where a part exceeds its
            # whole; publishing that as a percentage would be worse than a gap
            if share > 100.5 or share < -0.5:
                dropped[0] += 1
                continue
            t2.append(ti); v2.append(round(share, 4))
        if not t2: continue
        k = list(r["k"]); k[ui] = new_ui
        out.append({"k": k, "t": t2, "v": v2})
        made += 1

    if not made:
        unit["ids"].pop(); unit["names"].pop()
        return f"{slug}: no matching totals"

    meta["n_series"] = len(out)
    meta["n_obs"] = sum(len(r["v"]) for r in out)
    meta.setdefault("derived_units", {})[new_code] = {
        "label": new_label, "over": dim_id,
        "total_code": dim["ids"][tot] if tot is not None else "+".join(dim["ids"][i] for i in sum_codes),
        "method": f"value divided by the {dim['name']} total, times 100",
    }
    save(mp, meta, out)
    return f"{slug}: +{made} derived series ({new_label}); {dropped[0]} impossible values dropped"

for slug in (sys.argv[1:] or PLAN):
    print(run(slug))
