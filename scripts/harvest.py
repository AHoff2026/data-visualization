#!/usr/bin/env python3
"""Harvest OECD SDMX structure + full data for every dataflow in the manifest.
Resumable: skips artefacts already present and non-trivially sized."""
import json, pathlib, sys, time, threading, urllib.request, urllib.error, gzip, io
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path.home()/"Documents/data-visualization"
STRUCT = ROOT/"meta/struct"; RAW = ROOT/"raw"; LOG = ROOT/"meta/harvest.log.jsonl"
STRUCT.mkdir(parents=True, exist_ok=True); RAW.mkdir(parents=True, exist_ok=True)
BASE = "https://sdmx.oecd.org/public/rest"
lock = threading.Lock()

def log(**kw):
    kw["t"] = time.strftime("%H:%M:%S")
    with lock:
        with LOG.open("a") as f: f.write(json.dumps(kw)+"\n")
        print(json.dumps(kw), flush=True)

def fetch(url, accept, timeout=900, tries=4):
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": accept, "Accept-Encoding": "gzip",
                "User-Agent": "Mozilla/5.0 (Macintosh) DataViz/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                return b, None
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (400, 404, 406, 413): return None, last   # no point retrying
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(min(60, 5 * 2**a))
    return None, last

def slug(r): return f'{r["agency"]}__{r["flow"]}'

def do_struct(r):
    p = STRUCT/f"{slug(r)}.json"
    if p.exists() and p.stat().st_size > 500: return "cached"
    url = f'{BASE}/dataflow/{r["agency"]}/{r["dataflow_id"]}/{r["version"]}?references=all'
    b, err = fetch(url, "application/vnd.sdmx.structure+json;version=1.0", timeout=300)
    if b is None:
        log(step="struct", flow=slug(r), ok=False, err=err); return "fail"
    p.write_bytes(b); log(step="struct", flow=slug(r), ok=True, bytes=len(b)); return "ok"

DATA_ACCEPT = "application/vnd.sdmx.data+csv; charset=utf-8; labels=both"

def do_data(r):
    p = RAW/f"{slug(r)}.csv"
    if p.exists() and p.stat().st_size > 200: return "cached"
    key = "all"
    url = f'{BASE}/data/{r["agency"]},{r["dataflow_id"]},{r["version"]}/{key}?format=csvfilewithlabels'
    b, err = fetch(url, DATA_ACCEPT)
    if b is not None and len(b) > 200:
        p.write_bytes(b)
        log(step="data", flow=slug(r), ok=True, bytes=len(b), rows=b.count(b"\n"))
        return "ok"
    # fallback: chunk by reference area using codelist from structure
    areas = ref_areas(r)
    if not areas:
        log(step="data", flow=slug(r), ok=False, err=err or "empty", fallback="none"); return "fail"
    log(step="data", flow=slug(r), ok=False, err=err or "empty", fallback=f"chunk/{len(areas)}")
    parts, header, got = [], None, 0
    for i in range(0, len(areas), 8):
        grp = "+".join(areas[i:i+8])
        u = f'{BASE}/data/{r["agency"]},{r["dataflow_id"]},{r["version"]}/{grp}?format=csvfilewithlabels'
        cb, cerr = fetch(u, DATA_ACCEPT, timeout=900, tries=3)
        if cb is None or len(cb) < 100: continue
        txt = cb.decode("utf-8", "replace").splitlines(True)
        if not txt: continue
        if header is None: header = txt[0]; parts.append(txt[0])
        parts.extend(txt[1:]); got += 1
    if not parts:
        log(step="data", flow=slug(r), ok=False, err="chunk-all-failed"); return "fail"
    p.write_text("".join(parts))
    log(step="data", flow=slug(r), ok=True, chunks=got, bytes=p.stat().st_size, mode="chunked")
    return "ok"

def ref_areas(r):
    """Pull REF_AREA codes from the harvested structure file."""
    p = STRUCT/f"{slug(r)}.json"
    if not p.exists(): return []
    try: d = json.loads(p.read_text())
    except Exception: return []
    for cl in d.get("data", {}).get("codelists", []):
        if "CL_AREA" in cl.get("id", "").upper() or "REF_AREA" in cl.get("id", "").upper():
            return [c["id"] for c in cl.get("codes", [])]
    return []

def main():
    flows = json.loads((ROOT/"meta/manifest.json").read_text())
    log(step="start", n=len(flows))
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(do_struct, flows))
    log(step="struct-done")
    res = {}
    with ThreadPoolExecutor(3) as ex:
        for r, out in zip(flows, ex.map(do_data, flows)):
            res[slug(r)] = out
    from collections import Counter
    log(step="done", **Counter(res.values()))
    (ROOT/"meta/harvest_result.json").write_text(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()
