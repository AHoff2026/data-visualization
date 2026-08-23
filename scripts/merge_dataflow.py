#!/usr/bin/env python3
"""Merge another dataflow into an existing dataset that shares its structure.

OECD splits one collection across several dataflows: a general table covering
every member, and a cyclical one carrying an extra breakdown for a subset. They
have the same dimensions and codelists, so the general table can fill the
general table's own gaps in place rather than sitting alongside as a near
duplicate.

Values that already exist are compared, never overwritten, and disagreements are
reported: two OECD tables of the same quantity must agree, and if they do not
that is worth knowing before either is trusted.

  python3 scripts/merge_dataflow.py <target-slug> <agency> <flow_id> <version>
"""
import csv, gzip, json, pathlib, sys, urllib.request
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
csv.field_size_limit(10**9)

def fetch_csv(agency, flow, version, dest):
    url = (f"https://sdmx.oecd.org/public/rest/data/{agency},{flow},{version}/all"
           f"?format=csvfilewithlabels")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.sdmx.data+csv; charset=utf-8; labels=both",
        "Accept-Encoding": "gzip", "User-Agent": "ForestAndTheTrees/1.0"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip": data = gzip.decompress(data)
    dest.write_bytes(data)
    return dest

def load(slug):
    d = SITE/"flows"/slug
    meta = json.loads((d/"meta.json").read_text())
    recs = []
    if meta["layout"] == "single":
        f = d/"all.json.gz"
        if f.exists(): recs = json.loads(gzip.decompress(f.read_bytes()))
    else:
        for info in (meta.get("parts") or {}).values():
            f = d/"parts"/info["file"]
            if f.exists(): recs += json.loads(gzip.decompress(f.read_bytes()))
    return meta, recs

def save(slug, meta, recs):
    d = SITE/"flows"/slug
    meta["n_series"] = len(recs); meta["n_obs"] = sum(len(r["v"]) for r in recs)
    if meta["layout"] == "single":
        (d/"all.json.gz").write_bytes(gzip.compress(
            json.dumps(recs, separators=(",", ":")).encode(), 6))
    else:
        ai = next((i for i, x in enumerate(meta["dims"]) if x["id"] == meta.get("area_dim")), None)
        if ai is None: continue
        codes = meta["dims"][ai]["ids"]
        by = defaultdict(list)
        for r in recs: by[codes[r["k"][ai]]].append(r)
        parts = {}
        (d/"parts").mkdir(exist_ok=True)
        for c, rs in by.items():
            fn = (meta.get("parts") or {}).get(c, {}).get("file") or (c + ".json.gz")
            blob = gzip.compress(json.dumps(rs, separators=(",", ":")).encode(), 6)
            (d/"parts"/fn).write_bytes(blob)
            parts[c] = {"file": fn, "n": len(rs), "bytes": len(blob)}
        meta["parts"] = parts
    (d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))

def main(slug, agency, flow, version):
    meta, recs = load(slug)
    dim_ids = [d["id"] for d in meta["dims"]]
    code_pos = [{c: i for i, c in enumerate(d["ids"])} for d in meta["dims"]]
    pidx = {p: i for i, p in enumerate(meta["periods"])}

    existing = {}
    for r in recs:
        for t, v in zip(r["t"], r["v"]): existing[(tuple(r["k"]), t)] = v

    tmp = ROOT/"raw"; tmp.mkdir(exist_ok=True)
    path = fetch_csv(agency, flow, version, tmp/f"_merge_{slug}.csv")
    print(f"  fetched {path.stat().st_size/1e6:.1f} MB")

    added = defaultdict(lambda: {"t": [], "v": []})
    same = differ = skipped = 0
    new_codes = defaultdict(dict); new_periods = set()
    with path.open(newline="", encoding="utf-8", errors="replace") as fh:
        rdr = csv.reader(fh); header = next(rdr)
        idx = {h: i for i, h in enumerate(header)}
        if any(d not in idx for d in dim_ids):
            print("  structures differ; aborting"); path.unlink(); return False
        di = [idx[d] for d in dim_ids]
        # label column sits right after each code column
        import re as _re
        is_label = lambda h: bool(h) and not _re.fullmatch(r'[A-Z0-9_]+', h)
        dl = [i+1 if i+1 < len(header) and is_label(header[i+1]) else None for i in di]
        ti, vi = idx.get(meta["time_dim"]), idx.get("OBS_VALUE")
        # First pass: learn every code and period the source uses, so the target
        # can be extended rather than skipping what it has not seen before.
        rows = list(rdr)
        for row in rows:
            if len(row) <= vi or not row[vi].strip(): continue
            for n, ci in enumerate(di):
                c = row[ci]
                if c not in code_pos[n]:
                    lbl = row[dl[n]] if dl[n] is not None and dl[n] < len(row) else ""
                    new_codes[n][c] = lbl or c
            if row[ti] not in pidx: new_periods.add(row[ti])

        for n, table in new_codes.items():
            for c, lbl in sorted(table.items()):
                meta["dims"][n]["ids"].append(c)
                meta["dims"][n]["names"].append(lbl)
                code_pos[n][c] = len(meta["dims"][n]["ids"]) - 1
        if new_periods:
            def pkey(x):
                m2 = _re.match(r'^(\d{4})(?:-?([QSM])?(\d{1,2}))?$', x)
                return (int(m2.group(1)), int(m2.group(3) or 0)) if m2 else (9999, 0)
            allp = sorted(set(meta["periods"]) | new_periods, key=pkey)
            remap = {old_i: allp.index(p) for old_i, p in enumerate(meta["periods"])}
            for r in recs:
                r["t"] = [remap[t] for t in r["t"]]
            existing = {}
            for r in recs:
                for t, v in zip(r["t"], r["v"]): existing[(tuple(r["k"]), t)] = v
            meta["periods"] = allp
            pidx = {p: i for i, p in enumerate(allp)}
        print(f"  extended: {sum(len(v) for v in new_codes.values())} codes, "
              f"{len(new_periods)} periods")

        for row in rows:
            if len(row) <= vi: continue
            raw = row[vi].strip()
            if not raw: continue
            try: val = round(float(raw), 6)
            except ValueError: continue
            key = [code_pos[n][row[ci]] for n, ci in enumerate(di)]
            per = row[ti]
            k = (tuple(key), pidx[per])
            if k in existing:
                if abs(existing[k] - val) < 1e-6: same += 1
                else: differ += 1
                continue
            a = added[tuple(key)]
            a["t"].append(pidx[per]); a["v"].append(val)
    path.unlink(missing_ok=True)

    n_new = sum(len(a["v"]) for a in added.values())
    print(f"  overlapping values: {same} agree, {differ} differ")
    print(f"  new observations: {n_new} in {len(added)} series")

    if differ > same * 0.01 and same:
        print("  too many disagreements; not merging"); return False

    by_key = {tuple(r["k"]): r for r in recs}
    for key, a in added.items():
        order = sorted(range(len(a["t"])), key=lambda i: a["t"][i])
        t2 = [a["t"][i] for i in order]; v2 = [a["v"][i] for i in order]
        if key in by_key:
            r = by_key[key]
            merged = dict(zip(r["t"], r["v"])); merged.update(dict(zip(t2, v2)))
            ks = sorted(merged)
            r["t"] = ks; r["v"] = [merged[k] for k in ks]
            r.pop("s", None)
        else:
            recs.append({"k": list(key), "t": t2, "v": v2})
    meta.setdefault("merged_from", []).append(
        {"flow": flow, "agency": agency, "new_observations": n_new,
         "overlap_agreed": same, "overlap_differed": differ})
    save(slug, meta, recs)
    print(f"  merged: {meta['n_series']} series, {meta['n_obs']:,} observations")
    return True

if __name__ == "__main__":
    sys.exit(0 if main(*sys.argv[1:5]) else 1)
