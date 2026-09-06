#!/usr/bin/env python3
"""Re-download every OECD dataset and compare it, value for value, to what we serve.

The claim under test is narrow and important: a number on this site is the number
the source published. Not rescaled, not rounded, not re-based, not shifted by a
period-axis edit. Seven datasets were checked before; this checks all of them.

A window of years is compared rather than the whole history, because the whole
history is gigabytes. The window is chosen to sit inside every dataset's span.

Resumable: results land in the scratchpad after each dataset, so an interrupted
run picks up where it stopped.
"""
import csv, gzip, io, json, os, pathlib, sys, urllib.error, urllib.request

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
OUT = pathlib.Path(os.environ.get("AUDIT_OUT",
      "/private/tmp/claude-501/-Users-alexhoffman-Documents/"
      "5b734f3a-e90a-44b8-ab72-abd591c4d0c9/scratchpad/fidelity"))
OUT.mkdir(parents=True, exist_ok=True)
LO, HI = os.environ.get("LO", "2015"), os.environ.get("HI", "2018")

def load(slug):
    d = FLOWS/slug
    m = json.loads((d/"meta.json").read_text())
    if m["layout"] == "single":
        f = d/"all.json.gz"
        r = json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    else:
        r = [x for f in sorted((d/"parts").glob("*.json.gz"))
             for x in json.loads(gzip.decompress(f.read_bytes()))]
    return m, r

def fetch(agency, flow, lo=None, hi=None):
    url = (f"https://sdmx.oecd.org/public/rest/data/{agency},{flow},/all"
           f"?format=csvfilewithlabels&startPeriod={lo or LO}&endPeriod={hi or HI}")
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.sdmx.data+csv; charset=utf-8; labels=both",
        "Accept-Encoding": "gzip", "User-Agent": "ForestAndTheTrees/1.0"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        b = r.read()
        if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
    return b.decode("utf-8", "replace")

live = {f["slug"] for f in json.loads((ROOT/"site/data/catalog.json").read_text())["flows"]}
targets = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    m = json.loads(mp.read_text())
    if m["slug"] in live and (m.get("agency") or "").startswith("OECD."):
        targets.append((m["slug"], m["agency"], m["id"]))
only = [a for a in sys.argv[1:] if not a.startswith("-")]
if only: targets = [t for t in targets if t[0] in only]
print(f"{len(targets)} OECD datasets to check, window {LO}-{HI}\n", flush=True)

for slug, agency, flow in targets:
    dest = OUT/f"{slug}.json"
    if dest.exists(): continue
    m, recs = load(slug)
    # A fixed window returns 404 for a dataset that does not reach it. Clamp the
    # window into the dataset's own span instead.
    yrs = sorted({p[:4] for p in m["periods"]})
    lo, hi = LO, HI
    if yrs and (HI < yrs[0] or LO > yrs[-1]):
        hi = yrs[-1]; lo = yrs[max(0, len(yrs)-4)]
    ids = [x["id"] for x in m["dims"]]
    D = {x["id"]: x for x in m["dims"]}
    P = m["periods"]
    ours = {}
    for r in recs:
        k = tuple(D[ids[i]]["ids"][v] for i, v in enumerate(r["k"]))
        for t, v in zip(r["t"], r["v"]):
            if lo <= P[t][:4] <= hi: ours[(k, P[t])] = v
    res = {"slug": slug, "name": m["name"], "window": [lo, hi],
           "ours_in_window": len(ours)}
    try:
        rows = list(csv.DictReader(io.StringIO(fetch(agency, flow, lo, hi))))
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        dest.write_text(json.dumps(res)); print(f"  {m['name'][:40]:42} FETCH FAILED {res['error'][:50]}", flush=True)
        continue
    matched = mism = unmatched = 0
    ex = []
    for row in rows:
        if not row.get("OBS_VALUE"): continue
        try: k = tuple(row[i] for i in ids)
        except KeyError: continue
        got = ours.get((k, row["TIME_PERIOD"]))
        if got is None: unmatched += 1; continue
        try: src = float(row["OBS_VALUE"])
        except ValueError: continue
        if abs(got - src) > max(1e-6, abs(src)*1e-9):
            mism += 1
            if len(ex) < 4: ex.append({"key": list(k), "period": row["TIME_PERIOD"],
                                       "source": src, "site": got})
        else: matched += 1
    res.update({"source_rows": len(rows), "matched": matched,
                "mismatched": mism, "source_keys_not_on_site": unmatched,
                "examples": ex})
    dest.write_text(json.dumps(res, indent=1))
    flag = "  MISMATCH" if mism else ""
    print(f"  {m['name'][:40]:42} matched {matched:>8,}  mismatched {mism:>5}"
          f"  source-only {unmatched:>7,}{flag}", flush=True)
print("\ndone", flush=True)
