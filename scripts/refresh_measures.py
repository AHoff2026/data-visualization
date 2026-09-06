#!/usr/bin/env python3
"""Replace specific measures in a dataset with the source's current values.

Used where an audit shows the stored values cannot be right and the source's
current ones can. Surgical rather than a full re-harvest: only the named
measures are touched, so editorial decisions elsewhere in the dataset survive.

  python3 scripts/refresh_measures.py <slug> MEASURE_A MEASURE_B ...
"""
import csv, gzip, io, json, pathlib, sys, urllib.request, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"

def fetch(agency, flow, key):
    url = (f"https://sdmx.oecd.org/public/rest/data/{agency},{flow},/{key}"
           "?format=csvfilewithlabels")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.sdmx.data+csv; charset=utf-8; labels=both",
        "Accept-Encoding": "gzip", "User-Agent": "ForestAndTheTrees/1.0"})
    with urllib.request.urlopen(req, timeout=2400) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
    return b.decode("utf-8", "replace")

slug, measures = sys.argv[1], set(sys.argv[2:])
REFRESH_ALL = measures == {"ALL"} or not measures
d = ROOT/"site/data/flows"/slug
meta = json.loads((d/"meta.json").read_text())
ids = [x["id"] for x in meta["dims"]]
D = {x["id"]: x for x in meta["dims"]}
P = meta["periods"]
mi = ids.index("MEASURE")

# the SDMX key needs the dataflow's own dimension order, so ask for everything
# and filter locally; the alternative is guessing at slot positions.
raw = fetch(meta["agency"], meta["id"], "all")
fresh = {}
for row in csv.DictReader(io.StringIO(raw)):
    if not row.get("OBS_VALUE"): continue
    if not REFRESH_ALL and row.get("MEASURE") not in measures: continue
    try: k = tuple(row[i] for i in ids)
    except KeyError: continue
    try: fresh[(k, row["TIME_PERIOD"])] = float(row["OBS_VALUE"])
    except ValueError: pass
print(f"source rows for {sorted(measures)}: {len(fresh):,}")

single = meta["layout"] == "single"
chunks = ({"all.json.gz": json.loads(gzip.decompress((d/"all.json.gz").read_bytes()))}
          if single else
          {f.name: json.loads(gzip.decompress(f.read_bytes()))
           for f in sorted((d/"parts").glob("*.json.gz"))})
replaced = dropped = kept = 0
for fn, recs in chunks.items():
    out = []
    for r in recs:
        code = D["MEASURE"]["ids"][r["k"][mi]]
        if not REFRESH_ALL and code not in measures:
            out.append(r); kept += len(r["v"]); continue
        k = tuple(D[ids[i]]["ids"][v] for i, v in enumerate(r["k"]))
        t2, v2 = [], []
        for t, v in zip(r["t"], r["v"]):
            nv = fresh.get((k, P[t]))
            if nv is None: dropped += 1; continue
            t2.append(t); v2.append(round(nv, 6)); replaced += 1
        if v2:
            n = dict(r); n["t"] = t2; n["v"] = v2
            n.pop("s", None)
            out.append(n)
    chunks[fn] = out

if single:
    (d/"all.json.gz").write_bytes(gzip.compress(
        json.dumps(chunks["all.json.gz"], separators=(",", ":")).encode(), 6))
else:
    for fn, recs in chunks.items():
        p = d/"parts"/fn
        p.write_bytes(gzip.compress(json.dumps(recs, separators=(",", ":")).encode(), 6))
        for code, info in (meta.get("parts") or {}).items():
            if isinstance(info, dict) and info.get("file") == fn:
                info["n"] = sum(len(r["v"]) for r in recs)
                info["bytes"] = p.stat().st_size
allrecs = [r for recs in chunks.values() for r in recs]
meta["n_series"] = len(allrecs)
meta["n_obs"] = sum(len(r["v"]) for r in allrecs)
(d/"meta.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f"replaced {replaced:,} values; dropped {dropped:,} the source no longer carries; "
      f"{kept:,} untouched")
