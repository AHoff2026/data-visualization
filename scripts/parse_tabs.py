import json, re, urllib.parse as up, pathlib

ROOT = pathlib.Path.home()/ "Documents/data-visualization"
lines = [l.strip() for l in (ROOT/"meta/tabs.txt").read_text().splitlines() if l.strip()]

out = []
skipped = []
for i, url in enumerate(lines):
    if "/vis?" not in url:
        skipped.append(url); continue
    q = url.split("?", 1)[1]
    # parse_qs with unquoting; keys arrive like df[id] or df%5Bid%5D
    params = {}
    for part in q.split("&"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = up.unquote(k)
        v = up.unquote(v)
        params[k] = v
    did = params.get("df[id]", "")
    if not did:
        skipped.append(url); continue
    # df[id] arrives as DSD_X%40DF_Y after one unquote (was %2540)
    did = up.unquote(did)
    if "@" not in did:
        skipped.append(url); continue
    dsd, flow = did.split("@", 1)
    rec = {
        "tab_index": i,
        "url": url,
        "agency": params.get("df[ag]", ""),
        "dsd": dsd,
        "flow": flow,
        "dataflow_id": did,
        "version": params.get("df[vs]", "1.0"),
        "default_key": params.get("dq", ""),
        "period": params.get("pd", ""),
        "last_n_mode": params.get("lom", ""),
        "last_n": params.get("lo", ""),
        "view": params.get("vw", ""),
        "topic_raw": params.get("fs[0]", ""),
        "theme": params.get("tm", ""),
        "page": params.get("pg", ""),
    }
    out.append(rec)

# dedupe by (agency, dataflow_id, version)
seen = {}
for r in out:
    k = (r["agency"], r["dataflow_id"], r["version"])
    if k not in seen:
        seen[k] = r
    else:
        seen[k].setdefault("dupe_tabs", []).append(r["tab_index"])

uniq = list(seen.values())
(ROOT/"meta/manifest.json").write_text(json.dumps(uniq, indent=2))
print(f"tabs parsed : {len(out)}")
print(f"unique flows: {len(uniq)}")
print(f"skipped     : {len(skipped)}")
for s in skipped: print("  SKIP:", s[:110])
print("\nagencies:")
from collections import Counter
for a, c in Counter(r["agency"] for r in uniq).most_common():
    print(f"  {a:24} {c}")
