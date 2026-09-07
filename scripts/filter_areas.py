#!/usr/bin/env python3
"""Keep OECD members and the regional aggregates; drop everyone else.

The site is for comparing OECD countries. Carrying 215 areas in a picker when
38 are ever wanted is clutter, and the non-member rows are a long tail nobody
opens.

Nothing here is irreversible: the payloads before this ran are in git history,
and re-running the dataset builders restores full coverage.

A country is kept if it is an OECD member or a regional aggregate. Accession
candidates and key partners -- Brazil, China, India, Indonesia, Russia, South
Africa -- are not members and go with the rest.
"""
import json, gzip, pathlib, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

OECD = {"AUS","AUT","BEL","CAN","CHL","COL","CRI","CZE","DNK","EST","FIN","FRA","DEU",
        "GRC","HUN","ISL","IRL","ISR","ITA","JPN","KOR","LVA","LTU","LUX","MEX","NLD",
        "NZL","NOR","POL","PRT","SVK","SVN","ESP","SWE","CHE","TUR","GBR","USA"}
AGG_PREFIX = ("EU", "EA", "OECD", "G7", "G20", "WLD", "EUOECD")

def keep(code):
    return code in OECD or code.startswith(AGG_PREFIX)

total_dropped = 0
rows = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    dims = meta["dims"]
    ai = next((i for i, d in enumerate(dims) if d["id"] == "REF_AREA"), None)
    if ai is None: continue
    A = dims[ai]
    keep_idx = [i for i, c in enumerate(A["ids"]) if keep(c)]
    if len(keep_idx) == len(A["ids"]): continue
    remap = {old: new for new, old in enumerate(keep_idx)}
    single = meta["layout"] == "single"

    def filt(recs):
        out = []
        for r in recs:
            if r["k"][ai] not in remap: continue
            k = list(r["k"]); k[ai] = remap[k[ai]]
            n = dict(r); n["k"] = k
            out.append(n)
        return out

    dropped = 0
    if single:
        f = mp.parent/"all.json.gz"
        recs = json.loads(gzip.decompress(f.read_bytes()))
        out = filt(recs)
        dropped = sum(len(r["v"]) for r in recs) - sum(len(r["v"]) for r in out)
        f.write_bytes(gzip.compress(json.dumps(out, separators=(",", ":")).encode(), 6))
        allrecs = out
    else:
        allrecs = []
        parts = meta.get("parts") or {}
        newparts = {}
        for code, info in list(parts.items()):
            fn = info["file"] if isinstance(info, dict) else info
            p = mp.parent/"parts"/pathlib.Path(fn).name
            if not p.exists(): continue
            recs = json.loads(gzip.decompress(p.read_bytes()))
            if not keep(code):
                dropped += sum(len(r["v"]) for r in recs)
                p.unlink()
                continue
            out = filt(recs)
            dropped += sum(len(r["v"]) for r in recs) - sum(len(r["v"]) for r in out)
            p.write_bytes(gzip.compress(json.dumps(out, separators=(",", ":")).encode(), 6))
            newparts[code] = {"file": p.name, "n": sum(len(r["v"]) for r in out),
                              "bytes": p.stat().st_size}
            allrecs += out
        meta["parts"] = newparts

    A["ids"] = [A["ids"][i] for i in keep_idx]
    A["names"] = [A["names"][i] for i in keep_idx]
    for extra in ("aggregates", "secondary"):
        if extra in A:
            A[extra] = sorted(remap[i] for i in A[extra] if i in remap)
    meta["n_series"] = len(allrecs)
    meta["n_obs"] = sum(len(r["v"]) for r in allrecs)
    mp.write_text(json.dumps(meta, separators=(",", ":")))
    total_dropped += dropped
    rows.append((meta["name"], len(keep_idx), dropped))

rows.sort(key=lambda r: -r[2])
print(f"{'dataset':46}{'areas kept':>12}{'obs dropped':>14}")
for n, k, d in rows[:14]:
    print(f"  {n[:44]:46}{k:>12}{d:>14,}")
print(f"\n{total_dropped:,} observations removed across {len(rows)} datasets")
