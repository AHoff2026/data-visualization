#!/usr/bin/env python3
"""Add one SDMX dataflow to the site, end to end.

Runs the whole pipeline for a single flow so existing datasets are untouched:
harvest, transform, resolve labels, enrich, respell, classify dials, clarify and
disambiguate codes, coverage, bundle. Deletes the raw CSV afterwards — they run
to gigabytes and the disk is small.

  python3 scripts/add_dataflow.py OECD.WISE.INE DSD_WISE_IDD@DF_IDD 1.0 [--featured]
"""
import json, subprocess, sys, pathlib, urllib.request, gzip, io, time

ROOT = pathlib.Path.home()/"Documents/data-visualization"
BASE = "https://sdmx.oecd.org/public/rest"

def fetch(url, accept, tries=4, timeout=900):
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": accept, "Accept-Encoding": "gzip",
                "User-Agent": "ForestAndTheTrees/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    b = gzip.decompress(b)
                return b
        except Exception as e:
            last = e; time.sleep(4 * (a + 1))
    raise RuntimeError(f"fetch failed: {url}: {last}")

def run(*cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode: print(r.stdout[-2000:], r.stderr[-2000:])
    return r.returncode == 0

def main(agency, flow_id, version, featured=False, key="all"):
    slug = f"{agency}__{flow_id.split('@')[-1]}"
    print(f"adding {slug}")

    (ROOT/"meta/struct").mkdir(parents=True, exist_ok=True)
    sp = ROOT/"meta/struct"/f"{slug}.json"
    if not sp.exists() or sp.stat().st_size < 500:
        sp.write_bytes(fetch(f"{BASE}/dataflow/{agency}/{flow_id}/{version}?references=all",
                             "application/vnd.sdmx.structure+json;version=1.0", timeout=300))
    print("  structure ok")

    (ROOT/"raw").mkdir(exist_ok=True)
    csv = ROOT/"raw"/f"{slug}.csv"
    if not csv.exists() or csv.stat().st_size < 200:
        csv.write_bytes(fetch(
            f"{BASE}/data/{agency},{flow_id},{version}/{key}?format=csvfilewithlabels",
            "application/vnd.sdmx.data+csv; charset=utf-8; labels=both"))
    print(f"  data ok ({csv.stat().st_size/1e6:.1f} MB)")

    # the manifest and catalog drive the rest of the pipeline
    man = json.loads((ROOT/"meta/manifest.json").read_text())
    if not any(r["agency"] == agency and r["flow"] == flow_id.split("@")[-1] for r in man):
        man.append({"agency": agency, "dsd": flow_id.split("@")[0], "flow": flow_id.split("@")[-1],
                    "dataflow_id": flow_id, "version": version, "default_key": "",
                    "period": "", "url": f"https://data-explorer.oecd.org/vis?df[id]={flow_id}"
                               f"&df[ag]={agency}&df[vs]={version}"})
        (ROOT/"meta/manifest.json").write_text(json.dumps(man, indent=2))

    if not run("python3", "scripts/build_catalog.py"): return False
    if not run("python3", "scripts/transform.py", slug): return False
    print("  transformed")
    for step in ("patch_labels.py", "enrich_meta.py", "americanize.py",
                 "classify_dims.py", "clarify_codes.py", "relabel_units.py",
                 "qualify_codes.py"):
        run("python3", f"scripts/{step}")
    run("python3", "scripts/clean_impossible.py")
    run("python3", "scripts/build_site_data.py")
    run("python3", "scripts/apply_editorial.py")
    run("python3", "scripts/coverage.py")
    run("python3", "scripts/build_default_bundles.py")
    csv.unlink(missing_ok=True)
    print("  raw csv removed")
    return True

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ok = main(args[0], args[1], args[2], "--featured" in sys.argv,
              args[3] if len(args) > 3 else "all")
    sys.exit(0 if ok else 1)
