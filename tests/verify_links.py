#!/usr/bin/env python3
"""Fetch every source link and check it resolves, and where it lands.

A dead or redirected source link is worse than no link: it says the number came
from somewhere checkable when it did not. This follows redirects and reports the
final URL, so a link that quietly lands on a search page or a "dataset moved"
notice shows up as such.
"""
import json, pathlib, urllib.request, urllib.error, collections, sys, time

ROOT = pathlib.Path.home()/"Documents/data-visualization"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ForestAndTheTrees/1.0"

live = {f["slug"] for f in json.loads((ROOT/"site/data/catalog.json").read_text())["flows"]}
targets = []
seen = set()
for mp in sorted((ROOT/"site/data/flows").glob("*/meta.json")):
    m = json.loads(mp.read_text())
    if m["slug"] not in live: continue
    for field in ("source_url", "docs_url", "licence_url", "license_url"):
        u = m.get(field)
        if u and (u, field) not in seen:
            seen.add((u, field))
            targets.append((m["name"], field, u))

print(f"{len(targets)} distinct links to check\n", flush=True)

class Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self): self.chain = []
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append((code, newurl))
        return super().redirect_request(req, fp, code, msg, headers, newurl)

rows = []
for name, field, url in targets:
    h = Redirects()
    op = urllib.request.build_opener(h)
    status, final, note = None, url, ""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method,
                                         headers={"User-Agent": UA,
                                                  "Accept": "text/html,*/*"})
            with op.open(req, timeout=90) as r:
                status = r.status
                final = r.url
            break
        except urllib.error.HTTPError as e:
            status = e.code
            final = getattr(e, "url", url)
            if method == "GET" or e.code not in (403, 405, 501): break
        except Exception as e:
            status = type(e).__name__
            if method == "GET": break
    # 403 from oecd.org and ilostat.ilo.org is bot protection, not a dead link:
    # both serve the page normally to a person. Calling those "failing" would be
    # a false alarm, so they are reported as unverifiable and left for a human.
    blocked = status in (403, 503)
    moved = final.rstrip("/") != url.rstrip("/")
    rows.append((name, field, url, status, final, moved, blocked))
    mark = ("ok " if status == 200 and not moved else
            "-> " if status == 200 else
            "?? " if blocked else "!! ")
    print(f"  {mark} {str(status):>18}  {url[:62]}", flush=True)
    if moved: print(f"        lands on: {final[:70]}", flush=True)
    time.sleep(0.5)

bad = [r for r in rows if r[3] != 200 and not r[6]]
blocked = [r for r in rows if r[6]]
moved = [r for r in rows if r[3] == 200 and r[5]]
print(f"\n{len(rows)} links: {len(rows)-len(bad)-len(moved)-len(blocked)} clean, "
      f"{len(moved)} redirected, {len(blocked)} bot-blocked (check by hand), "
      f"{len(bad)} genuinely failing")
json.dump([{"name": r[0], "field": r[1], "url": r[2], "status": str(r[3]),
            "final": r[4], "moved": r[5], "blocked": r[6]} for r in rows],
          open(ROOT/".audit/links.json", "w"), indent=1)
if blocked:
    print("\nbot-blocked, not verifiable from a script:")
    for r in blocked: print(f"   {str(r[3]):>5}  {r[0][:34]:36} {r[2][:60]}")
if bad:
    print("\ngenuinely failing:")
    for r in bad: print(f"   {str(r[3]):>5}  {r[0][:34]:36} {r[2][:60]}")
raise SystemExit(1 if bad else 0)
