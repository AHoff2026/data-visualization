#!/usr/bin/env python3
"""Check whether every series in dataset A also exists, value for value, in B.

Removing a dataset is only safe when nothing in it is unique. This compares all
series at full precision, with no minimum length, and reports exactly what would
be lost.
"""
import json, gzip, pathlib, hashlib, sys
from collections import defaultdict

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

def load(slug):
    d = FLOWS/slug
    m = json.loads((d/"meta.json").read_text())
    recs = []
    if m["layout"] == "single":
        f = d/"all.json.gz"
        if f.exists(): recs = json.loads(gzip.decompress(f.read_bytes()))
    else:
        for info in (m.get("parts") or {}).values():
            f = d/"parts"/info["file"]
            if f.exists(): recs += json.loads(gzip.decompress(f.read_bytes()))
    return m, recs

def prints(slug):
    m, recs = load(slug)
    per = m["periods"]
    out = defaultdict(int)
    for r in recs:
        h = hashlib.blake2b(
            ("|".join(f"{per[t]}:{v:.6g}" for t, v in zip(r["t"], r["v"]))).encode(),
            digest_size=12).hexdigest()
        out[h] += 1
    return m, out

def check(a, b):
    ma, fa = prints(a)
    mb, fb = prints(b)
    missing = {h: n for h, n in fa.items() if h not in fb}
    return {
        "a": a, "a_name": ma["name"], "b": b, "b_name": mb["name"],
        "a_series": sum(fa.values()), "unique_to_a": sum(missing.values()),
        "contained": not missing,
    }

CANDIDATES = [
 ("OECD.EDU.IMEP__DF_LSO_EARN_REL_MALE", "OECD.EDU.IMEP__DF_LSO_EARN_ALL"),
 ("OECD.ELS.SPD__DF_NET_GDP",            "OECD.ELS.SPD__DF_SOCX_AGG"),
 ("OECD.SDD.NAD__DF_TABLE2_B6_VPVOP",    "OECD.SDD.NAD__DF_TABLE2"),
 ("OECD.SDD.NAD__DF_TABLE2_B5N_HVPVOB",  "OECD.SDD.NAD__DF_TABLE2"),
 ("OECD.SDD.TPS__DF_ALFS_EMP_ICSE93",    "OECD.SDD.TPS__DF_ALFS_EMP"),
 ("OECD.ELS.SPD__DF_PUB_FAM",            "OECD.ELS.SPD__DF_SOCX_AGG"),
 ("OECD.ELS.SPD__DF_PUB_DIS_SIC",        "OECD.ELS.SPD__DF_SOCX_AGG"),
 ("OECD.ELS.SPD__DF_PUB_PRV",            "OECD.ELS.SPD__DF_SOCX_AGG"),
]
res = [check(a, b) for a, b in CANDIDATES]
(ROOT/"meta/containment.json").write_text(json.dumps(res, indent=1))
print(f"{'contained':>10} {'series':>8} {'unique':>7}  candidate / superset")
for r in res:
    print(f'{"YES" if r["contained"] else "no":>10} {r["a_series"]:8} {r["unique_to_a"]:7}  '
          f'{r["a_name"][:40]:40} / {r["b_name"][:36]}')
