#!/usr/bin/env python3
"""Move built flow payloads under site/data and emit a slim site catalog."""
import json, pathlib, shutil, gzip

ROOT = pathlib.Path.home()/"Documents/data-visualization"
SITE = ROOT/"site/data"
SITE.mkdir(parents=True, exist_ok=True)

src = ROOT/"data/flows"
dst = SITE/"flows"
dst.mkdir(parents=True, exist_ok=True)
# Merge, never replace. This once deleted every published payload because a
# single new dataset had been transformed into data/flows.
moved = 0
if src.exists():
    for d in sorted(src.iterdir()):
        if not d.is_dir(): continue
        target = dst/d.name
        if target.exists(): shutil.rmtree(target)
        shutil.move(str(d), str(target))
        moved += 1
    if not any(src.iterdir()): src.rmdir()
print(f"flow payloads moved into place: {moved}")

cat = json.loads((ROOT/"meta/catalog.json").read_text())
known = {f["slug"] for f in cat["flows"]}
on_disk = {d.name for d in (SITE/"flows").iterdir() if d.is_dir()}
missing = on_disk - known
if missing:
    print(f"warning: {len(missing)} payloads are on disk but not in the catalog: "
          f"{sorted(missing)[:4]}")
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
    "sample_countries": cat.get("sample_countries", cat["default_countries"]),
    "core_areas": cat.get("core_areas", cat["default_countries"]),
    "topic_tree": prune(cat["topic_tree"]),
    "flows": flows,
}
p = SITE/"catalog.json"
p.write_text(json.dumps(slim, separators=(",", ":")))
print(f'catalog.json: {p.stat().st_size/1024:.0f} KB, {len(flows)} flows')
print(f'total obs   : {sum(f["n_obs"] for f in flows):,}')
