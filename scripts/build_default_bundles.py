#!/usr/bin/env python3
"""Pre-build a small first-paint bundle for partitioned flows.

The bundle holds only the default countries AND the dimension values OECD's own
DEFAULT annotation selects — which is exactly what the opening view draws. The
full per-area parts are fetched in the background afterwards, so the controls
regain complete availability without delaying first paint.
"""
import json, gzip, pathlib

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
DEFAULTS = json.loads((ROOT/"site/data/catalog.json").read_text())["default_countries"]
TOTALISH = ["_T", "_Z", "TOT", "T"]
CAP = 1_200_000          # bytes; above this the bundle is not worth shipping

import re
RATE = re.compile(r'percent|per cent|^%|share of', re.I)
PERCAP = re.compile(r'per capita|per person|per head|per employee|per worker|per hour', re.I)
RATIO = re.compile(r'\brate\b|ratio|per 1 ?000|per thousand|per 100', re.I)

def unit_rank(name):
    """Mirror of unitRank() in site/js/series.js — the bundle must contain the
    unit the client will actually open on."""
    n = name or ""
    if RATE.search(n): return 6
    if PERCAP.search(n): return 5
    if RATIO.search(n): return 4
    if re.search(r'index', n, re.I): return 3
    if re.search(r'dollar|euro|currency|ppp', n, re.I): return 2
    if re.match(r'^(persons?|number|thousands?|millions?|units?|households?|head)', n, re.I): return 0
    return 1

def default_pick(dim, oecd):
    if dim["id"] in ("UNIT_MEASURE", "MEASURE"):
        best, best_sc = None, -1
        for j, nm in enumerate(dim["names"]):
            sc = unit_rank(nm) if dim["id"] == "UNIT_MEASURE" else (
                5 if re.search(r'\brate\b|percent|share|ratio|per capita', nm or "", re.I) else 1)
            if oecd.get(dim["id"]) and dim["ids"][j] == str(oecd[dim["id"]]).split("+")[0]:
                sc += 0.5
            if sc > best_sc: best_sc, best = sc, j
        if best is not None and best_sc >= (3 if dim["id"] == "UNIT_MEASURE" else 5):
            return best
    code = oecd.get(dim["id"])
    if code:
        j = dim["ids"].index(code.split("+")[0]) if code.split("+")[0] in dim["ids"] else -1
        if j >= 0: return j
    for t in TOTALISH:
        if t in dim["ids"]: return dim["ids"].index(t)
    return None

made = skipped = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    meta.pop("default_bundle", None)
    if meta.get("layout") != "parts":
        mp.write_text(json.dumps(meta, separators=(",", ":"))); skipped += 1; continue

    parts = meta.get("parts") or {}
    want = [c for c in DEFAULTS if c in parts] or list(parts)[:12]
    area_dim = meta.get("area_dim")
    dims = meta["dims"]
    ai = next((i for i, d in enumerate(dims) if d["id"] == area_dim), None)
    oecd = meta.get("oecd_defaults") or {}

    # fix every dimension except the area to its default value
    picks = {}
    for i, d in enumerate(dims):
        if i == ai or len(d["ids"]) <= 1: continue
        j = default_pick(d, oecd)
        if j is not None: picks[i] = j

    loaded = {}
    for c in want:
        f = mp.parent/"parts"/parts[c]["file"]
        if f.exists(): loaded[c] = json.loads(gzip.decompress(f.read_bytes()))

    def matching(pk):
        out = []
        for rs in loaded.values():
            out.extend(r for r in rs if all(r["k"][i] == j for i, j in pk.items()))
        return out

    recs = matching(picks)
    if not recs and loaded:
        # OECD's declared defaults do not occur in this data. Adopt the real
        # combination closest to them — the same rule the client uses — so the
        # bundle stays small instead of falling back to everything.
        first = next(iter(loaded.values()))
        best, best_score = None, -1
        for r in first:
            sc = sum(1 for i, j in picks.items() if r["k"][i] == j)
            if sc > best_score: best_score, best = sc, r
        if best is not None:
            picks = {i: best["k"][i] for i in picks}
            recs = matching(picks)
    if not recs:
        recs = [r for rs in loaded.values() for r in rs]
        picks = {}

    blob = gzip.compress(json.dumps(recs, separators=(",", ":")).encode(), 6)
    bundle_file = mp.parent/"default.json.gz"
    if len(blob) > CAP:
        bundle_file.unlink(missing_ok=True)
        print(f'{mp.parent.name:44} SKIP bundle {len(blob)/1024:.0f} KB > cap')
        skipped += 1
    else:
        bundle_file.write_bytes(blob)
        meta["default_bundle"] = {
            "areas": want, "bytes": len(blob), "n": len(recs),
            "picks": {dims[i]["id"]: dims[i]["ids"][j] for i, j in picks.items()},
            "partial": bool(picks),
        }
        made += 1
        print(f'{mp.parent.name:44} {len(want):2} areas {len(recs):7} series {len(blob)/1024:8.0f} KB'
              + ("  (partial)" if picks else ""))
    mp.write_text(json.dumps(meta, separators=(",", ":")))

print(f"\nbundles: {made}   skipped: {skipped}")
