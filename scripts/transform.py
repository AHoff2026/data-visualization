#!/usr/bin/env python3
"""CSV -> compact per-flow series JSON.

Output per flow (data/flows/<slug>/):
  meta.json    dims + code tables (only codes present) + period axis + stats
  all.json     every series, if small enough
  parts/<REF_AREA>.json + index in meta, if large
Series: {"k":[dimCodeIdx...], "t":[periodIdx...], "v":[num...], "s":[statusIdx...], "m":unitMult}
"""
import csv, json, gzip, pathlib, sys, re, math
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
RAW, OUT = ROOT/"raw", ROOT/"data/flows"
OUT.mkdir(parents=True, exist_ok=True)
csv.field_size_limit(10**9)
PART_THRESHOLD = 3_000_000   # bytes of compact JSON before partitioning by area

def period_sort_key(p):
    m = re.match(r'^(\d{4})(?:-?(Q|S|M)?(\d{1,2}))?$', p)
    if m:
        y = int(m.group(1)); sub = int(m.group(3) or 0)
        return (y, sub)
    m = re.match(r'^(\d{4})-(\d{2})$', p)
    if m: return (int(m.group(1)), int(m.group(2)))
    return (9999, 0)

def transform(slug, catflow):
    src = RAW/f"{slug}.csv"
    if not src.exists(): return {"slug": slug, "status": "missing"}
    dim_ids = [d["id"] for d in catflow["dimensions"]]
    tdim = catflow["time_dimension"]
    dim_ids = [d for d in dim_ids if d != tdim]

    code_name = {d: {} for d in dim_ids}          # code -> label
    status_name = {}
    series = defaultdict(lambda: {"t": [], "v": [], "s": [], "m": 0})
    periods = set()
    nrows = nobs = 0

    with src.open(newline="", encoding="utf-8", errors="replace") as fh:
        rdr = csv.reader(fh)
        header = next(rdr)
        idx = {h: i for i, h in enumerate(header)}
        missing = [d for d in dim_ids if d not in idx]
        if missing: return {"slug": slug, "status": "dim-missing", "missing": missing}
        di = [idx[d] for d in dim_ids]
        # label column sits right after each code column; code columns are
        # ALL-CAPS ids, label columns are human text ("Reference area")
        def is_label(h): return bool(h) and not re.fullmatch(r'[A-Z0-9_]+', h)
        dl = [i+1 if i+1 < len(header) and is_label(header[i+1]) else None for i in di]
        ti, vi = idx.get(tdim), idx.get("OBS_VALUE")
        si  = idx.get("OBS_STATUS")
        mi  = idx.get("UNIT_MULT")
        if ti is None or vi is None:
            return {"slug": slug, "status": "no-time-or-value"}

        for row in rdr:
            nrows += 1
            if len(row) <= vi: continue
            raw = row[vi].strip()
            if raw == "": continue                      # drop empty observations
            try: val = float(raw)
            except ValueError: continue
            key = []
            for n, ci in enumerate(di):
                c = row[ci] if ci < len(row) else ""
                key.append(c)
                if c not in code_name[dim_ids[n]]:
                    lab = row[dl[n]] if dl[n] is not None and dl[n] < len(row) else ""
                    code_name[dim_ids[n]][c] = lab or c
            per = row[ti]
            periods.add(per)
            st = row[si] if si is not None and si < len(row) else ""
            if st and st not in status_name: status_name[st] = st
            mult = 0
            if mi is not None and mi < len(row):
                try: mult = int(row[mi] or 0)
                except ValueError: mult = 0
            s = series[tuple(key)]
            s["t"].append(per); s["v"].append(val); s["s"].append(st); s["m"] = mult
            nobs += 1

    if not series: return {"slug": slug, "status": "no-data", "rows": nrows}

    plist = sorted(periods, key=period_sort_key)
    pidx = {p: i for i, p in enumerate(plist)}
    codes = {}
    for d in dim_ids:
        cs = sorted(code_name[d].items())
        codes[d] = {"ids": [c for c, _ in cs], "names": [n for _, n in cs],
                    "map": {c: i for i, (c, _) in enumerate(cs)}}
    slist = sorted(status_name)
    smap = {s: i for i, s in enumerate(slist)}

    def pack(key, s):
        order = sorted(range(len(s["t"])), key=lambda i: pidx[s["t"][i]])
        rec = {
            "k": [codes[d]["map"][key[n]] for n, d in enumerate(dim_ids)],
            "t": [pidx[s["t"][i]] for i in order],
            "v": [round(s["v"][i], 6) for i in order],
        }
        st = [smap.get(s["s"][i], -1) for i in order]
        if any(x >= 0 and slist[x] not in ("A", "") for x in st): rec["s"] = st
        if s["m"]: rec["m"] = s["m"]
        return rec

    packed = [pack(k, v) for k, v in series.items()]
    area_dim = "REF_AREA" if "REF_AREA" in dim_ids else None

    meta = {
        "slug": slug, "id": catflow["id"], "name": catflow["name"],
        "agency": catflow["agency"], "version": catflow["version"],
        "description": catflow["description"], "topic": catflow["topic"],
        "source_url": catflow["source_url"],
        "dims": [{"id": d, "name": next(x["name"] for x in catflow["dimensions"] if x["id"] == d),
                  "ids": codes[d]["ids"], "names": codes[d]["names"]} for d in dim_ids],
        "time_dim": tdim, "periods": plist,
        "statuses": slist,
        "area_dim": area_dim,
        "n_series": len(packed), "n_obs": nobs, "n_rows_read": nrows,
    }

    d = OUT/slug; d.mkdir(parents=True, exist_ok=True)
    body = json.dumps(packed, separators=(",", ":"))
    if len(body) <= PART_THRESHOLD or not area_dim:
        meta["layout"] = "single"
        (d/"all.json.gz").write_bytes(gzip.compress(body.encode(), 6))
        size = (d/"all.json.gz").stat().st_size
    else:
        meta["layout"] = "parts"
        ai = dim_ids.index(area_dim)
        parts = defaultdict(list)
        for rec in packed: parts[codes[area_dim]["ids"][rec["k"][ai]]].append(rec)
        (d/"parts").mkdir(exist_ok=True)
        pmeta, size = {}, 0
        for code, recs in parts.items():
            b = gzip.compress(json.dumps(recs, separators=(",", ":")).encode(), 6)
            fn = re.sub(r'[^A-Za-z0-9_.-]', '_', code) or "_"
            (d/"parts"/f"{fn}.json.gz").write_bytes(b)
            pmeta[code] = {"file": f"{fn}.json.gz", "n": len(recs), "bytes": len(b)}
            size += len(b)
        meta["parts"] = pmeta
    (d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
    return {"slug": slug, "status": "ok", "series": len(packed), "obs": nobs,
            "rows": nrows, "layout": meta["layout"], "bytes": size,
            "src_mb": round(src.stat().st_size/1e6, 1)}

def main():
    cat = json.loads((ROOT/"meta/catalog.json").read_text())
    only = sys.argv[1:] or None
    res = []
    for f in cat["flows"]:
        if only and f["slug"] not in only: continue
        try: r = transform(f["slug"], f)
        except Exception as e:
            r = {"slug": f["slug"], "status": "error", "err": f"{type(e).__name__}: {e}"}
        res.append(r); print(json.dumps(r), flush=True)
    (ROOT/"meta/transform_result.json").write_text(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
