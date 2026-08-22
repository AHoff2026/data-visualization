#!/usr/bin/env python3
"""Drop observations that contradict their own unit.

A share of respondents cannot be 68 million, and a count of persons cannot be
negative. These are publication errors, and a single one rescales a whole chart
so that every real value becomes a flat line. Removed here, and counted, rather
than silently plotted.
"""
import json, gzip, pathlib, re
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
BOUNDED = re.compile(r"percentage of (the )?(population|employment|labor force|"
                     r"labour force|employees|students|respondents|households|unemployed|"
                     r"working-age population)", re.I)
COUNT = re.compile(r"^(persons?|number|thousands?|households?)", re.I)
GROWTH = re.compile(r"growth|change", re.I)

def load(mp, meta):
    d = mp.parent
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for info in (meta.get("parts") or {}).values():
        f = d/"parts"/info["file"]
        if f.exists(): out += json.loads(gzip.decompress(f.read_bytes()))
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
        for c, rs in by.items():
            fn = (meta.get("parts") or {}).get(c, {}).get("file") or (c + ".json.gz")
            blob = gzip.compress(json.dumps(rs, separators=(",", ":")).encode(), 6)
            (d/"parts"/fn).write_bytes(blob)
            parts[c] = {"file": fn, "n": len(rs), "bytes": len(blob)}
        meta["parts"] = parts
    mp.write_text(json.dumps(meta, separators=(",", ":")))

total = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    ui = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "UNIT_MEASURE"), None)
    ti = next((i for i, d in enumerate(meta["dims"]) if d["id"] == "TRANSFORMATION"), None)
    if ui is None: continue
    recs = load(mp, meta)
    if not recs: continue
    dropped = 0; out = []
    for r in recs:
        if ti is not None and GROWTH.search(meta["dims"][ti]["names"][r["k"][ti]]):
            out.append(r); continue
        un = meta["dims"][ui]["names"][r["k"][ui]]
        bounded, count = bool(BOUNDED.search(un)), bool(COUNT.match(un))
        if not (bounded or count): out.append(r); continue
        t2, v2, s2 = [], [], []
        for j, (ti2, v) in enumerate(zip(r["t"], r["v"])):
            if (bounded and (v > 100.5 or v < -0.5)) or (count and v < 0):
                dropped += 1; continue
            t2.append(ti2); v2.append(v)
            if r.get("s"): s2.append(r["s"][j])
        if not t2: continue
        n = dict(r); n["t"] = t2; n["v"] = v2
        if r.get("s"): n["s"] = s2
        out.append(n)
    if dropped:
        meta["n_series"] = len(out); meta["n_obs"] = sum(len(x["v"]) for x in out)
        meta.setdefault("source_notes", []).append(
            f"{dropped} observation{'s' if dropped != 1 else ''} removed as impossible "
            f"for the stated unit — a share outside 0 to 100, or a negative count. "
            f"These are errors in the published table, not gaps.")
        save(mp, meta, out)
        total += dropped
        print(f'  {meta["name"][:46]:46} {dropped:6} removed')
print(f"\nimpossible observations removed: {total}")
