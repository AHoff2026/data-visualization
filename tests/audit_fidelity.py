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
import csv, gzip, io, json, os, pathlib, sys, time, urllib.error, urllib.request

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
    # OECD rate-limits a long audit. A 429 is not an answer about the data, so
    # back off and ask again rather than recording it as a result.
    delay = 60
    for attempt in range(8):
        try:
            with urllib.request.urlopen(req, timeout=1800) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip": b = gzip.decompress(b)
            return b.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or attempt == 5: raise
            wait = max(int(e.headers.get("Retry-After") or 0), delay)
            print(f"      rate limited, waiting {wait}s", flush=True)
            time.sleep(wait); delay = min(delay*2, 900)
    raise RuntimeError("unreachable")

live = {f["slug"] for f in json.loads((ROOT/"site/data/catalog.json").read_text())["flows"]}
targets = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    m = json.loads(mp.read_text())
    if m["slug"] in live and (m.get("agency") or "").startswith("OECD."):
        targets.append((m["slug"], m["agency"], m["id"]))
only = [a for a in sys.argv[1:] if not a.startswith("-")]
if only: targets = [t for t in targets if t[0] in only]
print(f"{len(targets)} OECD datasets to check, window {LO}-{HI}\n", flush=True)

# A cached result is a result: report it rather than skipping in silence. A run
# that printed nothing and said "done" once looked exactly like a clean pass.
# Pass --fresh to ignore the cache and re-download.
FRESH = "--fresh" in sys.argv
cached = 0
for slug, agency, flow in targets:
    dest = OUT/f"{slug}.json"
    if dest.exists() and not FRESH:
        try: r = json.loads(dest.read_text())
        except Exception: r = None
        if r and "matched" in r:
            cached += 1
            n_obs = r.get("n_obs") or json.loads(
                (FLOWS/slug/"meta.json").read_text()).get("n_obs", 0)
            cov = r["matched"]/(n_obs or 1)*100
            flag = "  MISMATCH" if r.get("mismatched") else ("  THIN" if cov < 25 else "")
            print(f"  {r.get('name', slug)[:40]:42} matched {r['matched']:>8,}"
                  f"  mismatched {r['mismatched']:>5}"
                  f"  covers {cov:>5.1f}% of the dataset  (cached){flag}", flush=True)
            continue
        if r and r.get("error"):
            print(f"  {slug[:40]:42} FETCH FAILED {r['error'][:50]}  (cached)", flush=True)
            cached += 1
            continue
        dest.unlink()
    if os.environ.get("THROTTLE"):
        time.sleep(float(os.environ["THROTTLE"]))
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
    res.update({"name": m["name"], "n_obs": m.get("n_obs", 0),
                "source_rows": len(rows), "matched": matched,
                "mismatched": mism, "source_keys_not_on_site": unmatched,
                "examples": ex})
    dest.write_text(json.dumps(res, indent=1))
    # Coverage belongs next to the verdict. "0 mismatched" over 4% of a dataset
    # is not the same claim as "0 mismatched" over all of it, and reporting the
    # two identically overstated how much of this site had actually been checked.
    cov = matched/(m.get("n_obs") or 1)*100
    flag = "  MISMATCH" if mism else ("  THIN" if cov < 25 else "")
    print(f"  {m['name'][:40]:42} matched {matched:>8,}  mismatched {mism:>5}"
          f"  covers {cov:>5.1f}% of the dataset{flag}", flush=True)
# A dataset that could not be fetched has not been verified. Saying "done" over
# a pile of fetch errors is how 33 unchecked datasets once looked like a pass.
errors = []
for slug, _a, _f in targets:
    d = OUT/f"{slug}.json"
    if d.exists():
        try:
            r = json.loads(d.read_text())
            if r.get("error"): errors.append((slug, r["error"][:60]))
        except Exception: errors.append((slug, "unreadable result"))
checked = len(targets) - cached
tm = tn = 0
for slug, _a, _f in targets:
    d = OUT/f"{slug}.json"
    if not d.exists(): continue
    try: r = json.loads(d.read_text())
    except Exception: continue
    tm += r.get("matched", 0)
    tn += r.get("n_obs") or json.loads(
        (FLOWS/slug/"meta.json").read_text()).get("n_obs", 0)
print(f"\ndone: {checked} re-downloaded, {cached} from cache "
      f"(--fresh to re-download everything)", flush=True)
if tn:
    print(f"coverage: {tm:,} of {tn:,} observations verified "
          f"({tm/tn*100:.1f}%). The default window is {LO}-{HI}; "
          f"set LO and HI to widen it.", flush=True)
if errors:
    print(f"\n{len(errors)} of {len(targets)} datasets were NOT verified:", flush=True)
    for slug, e in errors[:8]: print(f"   {slug:44} {e}", flush=True)
    raise SystemExit(f"{len(errors)} datasets could not be fetched; rerun to finish them")
if checked == 0 and cached == 0:
    raise SystemExit("nothing was checked")
