#!/usr/bin/env python3
"""For partitioned flows, pre-bundle the default countries into one file so the
first paint costs a single request instead of a dozen."""
import json, gzip, pathlib

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
DEFAULTS = json.loads((ROOT/"site/data/catalog.json").read_text())["default_countries"]

made = skipped = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    if meta.get("layout") != "parts":
        skipped += 1; continue
    parts = meta.get("parts") or {}
    want = [c for c in DEFAULTS if c in parts]
    if not want:
        want = list(parts)[:12]
    recs = []
    for c in want:
        f = mp.parent/"parts"/parts[c]["file"]
        if f.exists():
            recs.extend(json.loads(gzip.decompress(f.read_bytes())))
    if not recs:
        skipped += 1; continue
    blob = gzip.compress(json.dumps(recs, separators=(",", ":")).encode(), 6)
    (mp.parent/"default.json.gz").write_bytes(blob)
    meta["default_bundle"] = {"areas": want, "bytes": len(blob), "n": len(recs)}
    mp.write_text(json.dumps(meta, separators=(",", ":")))
    made += 1
    print(f'{mp.parent.name:44} {len(want):2} areas  {len(recs):7} series  {len(blob)/1024:8.0f} KB')

print(f"\nbundles: {made}   single-layout flows skipped: {skipped}")
