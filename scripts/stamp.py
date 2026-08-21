#!/usr/bin/env python3
"""Stamp css/js with a content hash so a deploy is never served stale.

GitHub Pages caches assets for ten minutes, and ES-module imports are fetched by
their own URL — versioning only the entry point leaves the rest of the graph
stale. This rewrites every relative import to carry the same version, and is
idempotent.
"""
import hashlib, pathlib, re

SITE = pathlib.Path(__file__).resolve().parent.parent / "site"
JS = sorted(SITE.glob("js/*.js"))

def strip(txt):
    return re.sub(r'(from\s+"\./[A-Za-z0-9_.-]+\.js)\?v=[0-9a-f]+"', r'\1"', txt)

# hash the unversioned sources so the version is stable for identical code
base = hashlib.sha1(b"".join(strip(p.read_text()).encode() for p in JS)).hexdigest()[:8]
cssv = hashlib.sha1((SITE / "css/app.css").read_bytes()).hexdigest()[:8]

for p in JS:
    txt = strip(p.read_text())
    out = re.sub(r'(from\s+"\./[A-Za-z0-9_.-]+\.js)"', rf'\1?v={base}"', txt)
    if out != p.read_text():
        p.write_text(out)

idx = SITE / "index.html"
s = idx.read_text()
s = re.sub(r'(href="css/app\.css)(\?v=[0-9a-f]+)?"', f'\\1?v={cssv}"', s)
s = re.sub(r'(src="js/app\.js)(\?v=[0-9a-f]+)?"', f'\\1?v={base}"', s)
idx.write_text(s)
print(f"stamped: js v={base}  css v={cssv}  ({len(JS)} modules)")
