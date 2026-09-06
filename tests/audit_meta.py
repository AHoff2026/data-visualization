#!/usr/bin/env python3
"""Audit what a reader meets: labels, definitions, defaults, coverage claims.

Data can be perfectly faithful and still unreadable. This checks the layer
between the number and the reader -- whether a dial says what it means, whether
an option is a code in disguise, whether a dataset opens on something worth
seeing, and whether it claims countries it barely covers.
"""
import json, gzip, pathlib, re, collections

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"
live = {f["slug"] for f in json.loads((ROOT/"site/data/catalog.json").read_text())["flows"]}

CODEY = re.compile(r"^[A-Z0-9_.\-]{2,}$")          # a label that is really a code
JARGON = re.compile(r"\b(n\.e\.c|ISCED|ISIC|NACE|COICOP|SNA|_[TZ]\b|excl\.|incl\.)", re.I)
findings = collections.defaultdict(list)

def load(d, m):
    if m["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    return [x for f in sorted((d/"parts").glob("*.json.gz"))
            for x in json.loads(gzip.decompress(f.read_bytes()))]

for mp in sorted(FLOWS.glob("*/meta.json")):
    m = json.loads(mp.read_text())
    if m["slug"] not in live: continue
    nm = m["name"]
    recs = load(mp.parent, m)
    ids = [x["id"] for x in m["dims"]]
    hidden = set((m.get("hidden_dims") or {}).keys())

    # -- description and notes
    if not (m.get("desc_html") or "").strip():
        findings["no description"].append(nm)
    if len(m.get("desc_text") or "") < 40:
        findings["thin description text"].append(nm)

    for i, d in enumerate(m["dims"]):
        if d["id"] == "REF_AREA": continue
        names = d.get("names") or []
        # -- a label that is still a code
        codey = [n for n in names if n and CODEY.fullmatch(n.strip())]
        if codey:
            findings["option labelled with a code"].append(f"{nm} / {d['name']}: {codey[:3]}")
        # -- the dial itself named with its SDMX id
        if d["name"] == d["id"] or CODEY.fullmatch(d["name"] or ""):
            findings["dial named with a code"].append(f"{nm}: {d['name']}")
        # -- duplicate option names inside one dial
        dup = [k for k, v in collections.Counter(names).items() if v > 1 and k]
        if dup:
            findings["two options with the same name"].append(f"{nm} / {d['name']}: {dup[:3]}")
        # -- classification jargon a reader cannot act on
        jar = [n for n in names if n and JARGON.search(n)]
        if len(jar) > 2:
            findings["classification jargon in labels"].append(
                f"{nm} / {d['name']}: {len(jar)} of {len(names)}")
        # -- very long labels
        long = [n for n in names if n and len(n) > 80]
        if long:
            findings["label over 80 characters"].append(f"{nm} / {d['name']}: {len(long)}")
        # -- an ordinal dial with no key
        if d.get("value_defs") is None and any(
                (u or "").lower().startswith("ordinal") for u in names):
            findings["ordinal scale without a key"].append(f"{nm} / {d['name']}")

    # -- coverage honesty: areas that carry almost nothing
    if recs and "REF_AREA" in ids:
        ai = ids.index("REF_AREA")
        A = m["dims"][ai]["ids"]
        c = collections.Counter()
        for r in recs: c[A[r["k"][ai]]] += len(r["v"])
        tot = sum(c.values())
        thin = [a for a in A if c[a] and c[a] / tot * 100 < 0.05]
        empty = [a for a in A if not c[a]]
        if empty:
            findings["country offered with no data at all"].append(f"{nm}: {len(empty)} areas")
        if len(thin) > 3:
            findings["country with under 0.05% of the data"].append(f"{nm}: {len(thin)} areas")

    # -- does the dataset's own default selection resolve to anything?
    if recs:
        pick = []
        for i, d in enumerate(m["dims"]):
            if d["id"] == "REF_AREA": pick.append(None); continue
            hv = (m.get("hidden_dims") or {}).get(d["id"])
            j = d["ids"].index(hv) if hv in d["ids"] else d.get("default", 0)
            pick.append(j)
        n = sum(len(r["v"]) for r in recs
                if all(p is None or r["k"][i] == p for i, p in enumerate(pick)))
        if n == 0:
            findings["default selection yields nothing"].append(nm)

print(f"{sum(len(v) for v in findings.values())} findings across "
      f"{len(findings)} categories\n")
for cat, items in sorted(findings.items(), key=lambda kv: -len(kv[1])):
    print(f"### {cat}  ({len(items)})")
    for x in items[:10]: print(f"    {x[:150]}")
    if len(items) > 10: print(f"    ... and {len(items)-10} more")
    print()
json.dump({k: v for k, v in findings.items()},
          open("/private/tmp/claude-501/-Users-alexhoffman-Documents/"
               "5b734f3a-e90a-44b8-ab72-abd591c4d0c9/scratchpad/audit_meta.json", "w"), indent=1)
