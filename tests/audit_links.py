#!/usr/bin/env python3
"""Check every link a reader can click actually resolves.

Source links and any links inside a description. A dead citation is worse than
no citation: it looks like provenance and provides none.
"""
import json, pathlib, re, urllib.request, urllib.error, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
live = {f["slug"] for f in json.loads((ROOT/"site/data/catalog.json").read_text())["flows"]}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"

urls = collections.defaultdict(set)
for mp in sorted((ROOT/"site/data/flows").glob("*/meta.json")):
    m = json.loads(mp.read_text())
    if m["slug"] not in live: continue
    if m.get("source_url"): urls[m["source_url"]].add(m["name"])
    for a in re.findall(r'href="([^"]+)"', m.get("desc_html") or ""):
        urls[a.replace("&amp;", "&")].add(m["name"])

print(f"{len(urls)} distinct links across {len(live)} datasets\n")
bad = []
for u in sorted(urls):
    if not u.startswith("http"): 
        bad.append((u, "not an http link", urls[u])); continue
    req = urllib.request.Request(u, headers={"User-Agent": UA}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=90) as r: code = r.status
    except urllib.error.HTTPError as e: code = e.code
    except Exception as e: code = type(e).__name__
    if code == 200: continue
    bad.append((u, code, urls[u]))
    print(f"  {str(code):>18}  {u[:96]}")
    for n in sorted(urls[u])[:3]: print(f"                      on: {n}")
print(f"\n{len(urls)-len(bad)} of {len(urls)} resolve; {len(bad)} did not")
json.dump([[u, str(c), sorted(n)] for u, c, n in bad],
          open("/private/tmp/claude-501/-Users-alexhoffman-Documents/"
               "5b734f3a-e90a-44b8-ab72-abd591c4d0c9/scratchpad/bad_links.json", "w"), indent=1)
