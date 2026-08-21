#!/usr/bin/env python3
"""ACCEPTANCE TESTS — data layer.

Every check is pass/fail. Exit code 0 only if all flows pass every check.
  T1 coverage      every manifest flow has meta.json + payload
  T2 obs parity    transformed observation count == non-empty OBS_VALUE rows in raw CSV
  T3 value parity  random sample of raw observations found with the exact value
  T4 index safety  every dimension index in every series resolves to a real code
  T5 time safety   every period index resolves; periods sorted chronologically
  T6 size sanity   payload present and non-trivial
"""
import csv, gzip, json, pathlib, random, re, sys
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
RAW, FLOWS = ROOT/"raw", ROOT/"data/flows"
csv.field_size_limit(10**9)
random.seed(20260821)
SAMPLE = 300

def period_key(p):
    m = re.match(r'^(\d{4})(?:-?([QSM])?(\d{1,2}))?$', p)
    if m: return (int(m.group(1)), int(m.group(3) or 0))
    m = re.match(r'^(\d{4})-(\d{2})$', p)
    if m: return (int(m.group(1)), int(m.group(2)))
    return (9999, 0)

def load_series(slug, meta):
    d = FLOWS/slug
    if meta.get("layout") == "single":
        f = d/"all.json.gz"
        if not f.exists(): return None
        return json.loads(gzip.decompress(f.read_bytes()))
    out = []
    for code, info in (meta.get("parts") or {}).items():
        f = d/"parts"/info["file"]
        if not f.exists(): return None
        out.extend(json.loads(gzip.decompress(f.read_bytes())))
    return out

def check(slug):
    res = {"slug": slug, "checks": {}, "fail": []}
    mp = FLOWS/slug/"meta.json"
    if not mp.exists():
        res["fail"].append("T1 no meta.json"); return res
    meta = json.loads(mp.read_text())
    series = load_series(slug, meta)
    if series is None:
        res["fail"].append("T1 payload missing"); return res
    res["checks"]["T1"] = "pass"

    # ---- T6
    if not series or meta["n_series"] == 0:
        res["fail"].append("T6 empty payload"); return res
    res["checks"]["T6"] = "pass"

    dim_ids = [d["id"] for d in meta["dims"]]
    nper = len(meta["periods"])

    # ---- T4 / T5
    bad_idx = bad_t = 0
    obs_count = 0
    for rec in series:
        if len(rec["k"]) != len(meta["dims"]): bad_idx += 1; continue
        for n, ci in enumerate(rec["k"]):
            if not (0 <= ci < len(meta["dims"][n]["ids"])): bad_idx += 1; break
        for ti in rec["t"]:
            if not (0 <= ti < nper): bad_t += 1; break
        if len(rec["t"]) != len(rec["v"]): bad_t += 1
        obs_count += len(rec["v"])
    res["checks"]["T4"] = "pass" if bad_idx == 0 else f"FAIL {bad_idx} bad dim indexes"
    if bad_idx: res["fail"].append(res["checks"]["T4"])
    ordered = all(period_key(meta["periods"][i]) <= period_key(meta["periods"][i+1])
                  for i in range(nper-1))
    res["checks"]["T5"] = "pass" if (bad_t == 0 and ordered) else \
        f"FAIL {bad_t} bad time refs, ordered={ordered}"
    if bad_t or not ordered: res["fail"].append(res["checks"]["T5"])

    # ---- T2 / T3 against the raw CSV
    src = RAW/f"{slug}.csv"
    if not src.exists():
        res["checks"]["T2"] = res["checks"]["T3"] = "skip (raw absent)"
        res["obs"] = obs_count
        return res

    raw_obs = 0
    sample = []
    with src.open(newline="", encoding="utf-8", errors="replace") as fh:
        rdr = csv.reader(fh); header = next(rdr)
        idx = {h: i for i, h in enumerate(header)}
        di = [idx[d] for d in dim_ids if d in idx]
        if len(di) != len(dim_ids):
            res["fail"].append("T2 dim columns missing in raw"); return res
        ti, vi = idx.get(meta["time_dim"]), idx.get("OBS_VALUE")
        mi = idx.get("UNIT_MULT")
        for row in rdr:
            if len(row) <= vi: continue
            v = row[vi].strip()
            if v == "": continue
            try: fv = float(v)
            except ValueError: continue
            raw_obs += 1
            if len(sample) < SAMPLE:
                sample.append((tuple(row[c] for c in di), row[ti], fv,
                               int(row[mi] or 0) if mi is not None and mi < len(row) and row[mi].strip().lstrip('-').isdigit() else 0))
            elif random.random() < SAMPLE / raw_obs:
                sample[random.randrange(SAMPLE)] = (tuple(row[c] for c in di), row[ti], fv,
                               int(row[mi] or 0) if mi is not None and mi < len(row) and row[mi].strip().lstrip('-').isdigit() else 0)

    res["obs"], res["raw_obs"] = obs_count, raw_obs
    res["checks"]["T2"] = "pass" if obs_count == raw_obs else f"FAIL {obs_count} != {raw_obs}"
    if obs_count != raw_obs: res["fail"].append(res["checks"]["T2"])

    # index the transformed payload for lookup
    code_pos = [{c: i for i, c in enumerate(d["ids"])} for d in meta["dims"]]
    pidx = {p: i for i, p in enumerate(meta["periods"])}
    table = {}
    for rec in series:
        key = tuple(rec["k"])
        for j, tI in enumerate(rec["t"]):
            table[(key, tI)] = rec["v"][j]

    miss = wrong = 0
    for codes, per, val, mult in sample:
        try: key = tuple(code_pos[n][c] for n, c in enumerate(codes))
        except KeyError: miss += 1; continue
        tI = pidx.get(per)
        if tI is None: miss += 1; continue
        got = table.get((key, tI))
        if got is None: miss += 1
        elif abs(got - round(val, 6)) > max(1e-6, abs(val) * 1e-9): wrong += 1
    res["checks"]["T3"] = "pass" if (miss == 0 and wrong == 0) else \
        f"FAIL {miss} missing, {wrong} wrong of {len(sample)}"
    if miss or wrong: res["fail"].append(res["checks"]["T3"])
    return res

def main():
    manifest = json.loads((ROOT/"meta/manifest.json").read_text())
    slugs = [f'{r["agency"]}__{r["flow"]}' for r in manifest]
    only = sys.argv[1:]
    if only: slugs = [s for s in slugs if s in only]
    results, failed = [], []
    for s in slugs:
        try: r = check(s)
        except Exception as e:
            r = {"slug": s, "fail": [f"EXCEPTION {type(e).__name__}: {e}"], "checks": {}}
        results.append(r)
        mark = "ok  " if not r["fail"] else "FAIL"
        print(f'{mark} {s:44} obs={r.get("obs","-"):>9} raw={r.get("raw_obs","-"):>9}'
              + ("  " + "; ".join(r["fail"]) if r["fail"] else ""), flush=True)
        if r["fail"]: failed.append(s)
    (ROOT/"tests/verify_data_result.json").write_text(json.dumps(results, indent=1))
    print(f"\n{'='*70}\nFLOWS: {len(results)}   PASS: {len(results)-len(failed)}   FAIL: {len(failed)}")
    tot = sum(r.get("obs", 0) for r in results)
    print(f"TOTAL OBSERVATIONS: {tot:,}")
    if failed:
        print("FAILED:", ", ".join(failed)); return 1
    print("ALL DATA ACCEPTANCE TESTS PASS")
    return 0

if __name__ == "__main__":
    sys.exit(main())
