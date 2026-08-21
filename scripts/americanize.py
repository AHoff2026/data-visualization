#!/usr/bin/env python3
"""Convert display text to American spelling. Applies to names and descriptions
only — never to codes, ids or values."""
import json, pathlib, re

PAIRS = [
    ("labour", "labor"), ("harmonised", "harmonized"), ("harmonisation", "harmonization"),
    ("organisation", "organization"), ("organised", "organized"),
    ("standardised", "standardized"), ("standardisation", "standardization"),
    ("utilisation", "utilization"), ("utilised", "utilized"),
    ("specialisation", "specialization"), ("specialised", "specialized"),
    ("centre", "center"), ("centres", "centers"),
    ("programme", "program"), ("programmes", "programs"),
    ("behaviour", "behavior"), ("behavioural", "behavioral"),
    ("favour", "favor"), ("favourable", "favorable"),
    ("defence", "defense"), ("licence", "license"),
    ("analyse", "analyze"), ("analysed", "analyzed"),
    ("catalogue", "catalog"), ("ageing", "aging"),
    ("modelling", "modeling"), ("travelling", "traveling"),
    ("per cent", "percent"), ("neighbouring", "neighboring"),
    ("recognised", "recognized"), ("characterised", "characterized"),
    ("categorised", "categorized"), ("normalised", "normalized"),
    ("fulfilment", "fulfillment"), ("enrolment", "enrollment"),
    ("practise", "practice"), ("prioritised", "prioritized"),
    ("summarised", "summarized"), ("emphasised", "emphasized"),
]
# longest first so "harmonisation" is not caught by "harmonised"
PAIRS.sort(key=lambda p: -len(p[0]))

def case_like(src, dst):
    if src.isupper(): return dst.upper()
    if src[:1].isupper(): return dst[:1].upper() + dst[1:]
    return dst

def fix(text):
    if not isinstance(text, str) or not text: return text
    out = text
    for uk, us in PAIRS:
        out = re.sub(rf'\b{uk}\b', lambda m: case_like(m.group(0), us), out, flags=re.I)
    return out

def walk(obj, keys):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in keys and isinstance(v, str): obj[k] = fix(v)
            elif k in keys and isinstance(v, list):
                obj[k] = [fix(x) if isinstance(x, str) else x for x in v]
            elif k == "code_defs" and isinstance(v, dict):
                obj[k] = {kk: fix(vv) for kk, vv in v.items()}
            else: walk(v, keys)
    elif isinstance(obj, list):
        for v in obj: walk(v, keys)

TEXT_KEYS = {"name", "names", "description", "desc_html", "desc_text", "def", "flow", "measure_name", "unit_name"}
ROOT = pathlib.Path.home()/"Documents/data-visualization"
n = 0
for f in sorted((ROOT/"site/data/flows").glob("*/meta.json")):
    d = json.loads(f.read_text()); before = json.dumps(d)
    walk(d, TEXT_KEYS)
    after = json.dumps(d)
    if before != after: f.write_text(json.dumps(d, separators=(",", ":"))); n += 1
c = ROOT/"site/data/catalog.json"
d = json.loads(c.read_text()); before = json.dumps(d)
walk(d, TEXT_KEYS)
if json.dumps(d) != before: c.write_text(json.dumps(d, separators=(",", ":")))
print(f"flows respelled: {n}")
