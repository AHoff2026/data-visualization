#!/usr/bin/env python3
"""Move built flow payloads under site/data and emit a slim site catalog."""
import json, pathlib, shutil, gzip

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SITE.mkdir(parents=True, exist_ok=True)

src = ROOT/"data/flows"
dst = SITE/"flows"
if src.exists():
    if dst.exists(): shutil.rmtree(dst)
    shutil.move(str(src), str(dst))
    print("moved flow payloads ->", dst)

cat = json.loads((ROOT/"meta/catalog.json").read_text())
flows = []
for f in cat["flows"]:
    mp = dst/f["slug"]/"meta.json"
    m = json.loads(mp.read_text()) if mp.exists() else {}
    flows.append({
        "slug": f["slug"], "id": f["id"], "name": f["name"],
        "agency": f["agency"], "topic": f["topic"],
        "description": (f["description"] or "")[:600],
        "n_series": m.get("n_series", 0), "n_obs": m.get("n_obs", 0),
        "periods": [m["periods"][0], m["periods"][-1]] if m.get("periods") else None,
        "layout": m.get("layout"),
        "source_url": f["source_url"],
    })

def prune(node):
    """Keep only topic-tree branches that lead to a dataset."""
    used = set()
    for f in flows:
        parts = str(f["topic"] or "").split(".")
        for i in range(1, len(parts)+1): used.add(".".join(parts[:i]))
    def walk(cats, prefix=""):
        out = []
        for c in cats:
            path = f'{prefix}{c["id"]}'
            kids = walk(c.get("categories", []), path + ".")
            if path in used or kids:
                out.append({"id": c["id"], "name": c.get("name") or c["id"],
                            **({"categories": kids} if kids else {})})
        return out
    return {"id": node["id"], "name": node.get("name"),
            "categories": walk(node.get("categories", []))}

slim = {
    "generated": cat["generated"],
    "default_countries": cat["default_countries"],
    "topic_tree": prune(cat["topic_tree"]),
    "flows": flows,
}
p = SITE/"catalog.json"
p.write_text(json.dumps(slim, separators=(",", ":")))
print(f'catalog.json: {p.stat().st_size/1024:.0f} KB, {len(flows)} flows')
print(f'total obs   : {sum(f["n_obs"] for f in flows):,}')
