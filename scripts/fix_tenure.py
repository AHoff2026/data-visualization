#!/usr/bin/env python3
"""Average job tenure: drop the zeros that are nulls, and name the two totals.

OECD publishes the United Kingdom's "Total" tenure as 0.0 with a normal-value
status for most years; the real figure sits under "Total declared". Nothing in
either label told a reader which was which, and "Total" was the default, so the
headline chart drew the United Kingdom as a flat line at zero next to Germany
at ten and a half years.

An average tenure of exactly zero years is not a measurement for any band that
starts at a month or more, so those are removed as the nulls they are. The bands
that legitimately average zero -- under one month -- are left alone.
"""
import json, gzip, pathlib

SLUG = "OECD.ELS.SAE__DF_TENURE_AVE"
D = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"/SLUG

LABEL = {"_T": "All employed, including tenure not stated",
         "TOTD": "All employed with a stated tenure"}
# bands whose average can legitimately be 0.0 years
ZERO_OK = {"M_LT1", "M_1T5"}

m = json.loads((D/"meta.json").read_text())
ids = [x["id"] for x in m["dims"]]
ti = ids.index("TENURE")
dim = m["dims"][ti]
for code, lab in LABEL.items():
    if code in dim["ids"]: dim["names"][dim["ids"].index(code)] = lab
# the reliable total leads
if "TOTD" in dim["ids"]: dim["default"] = dim["ids"].index("TOTD")

single = m["layout"] == "single"
if single:
    recs = json.loads(gzip.decompress((D/"all.json.gz").read_bytes()))
else:
    recs = []
    for f in sorted((D/"parts").glob("*.json.gz")):
        recs += json.loads(gzip.decompress(f.read_bytes()))
ok = {dim["ids"].index(c) for c in ZERO_OK if c in dim["ids"]}
out, dropped, emptied = [], 0, 0
for r in recs:
    if r["k"][ti] in ok: out.append(r); continue
    t2, v2 = [], []
    for t, v in zip(r["t"], r["v"]):
        if v == 0: dropped += 1; continue
        t2.append(t); v2.append(v)
    if not v2: emptied += 1; continue
    n = dict(r); n["t"] = t2; n["v"] = v2
    if r.get("s"): n["s"] = [s for s, v in zip(r["s"], r["v"]) if v != 0]
    out.append(n)

m["n_series"] = len(out); m["n_obs"] = sum(len(r["v"]) for r in out)
if (m.get("default_bundle") or {}).get("picks", {}).get("TENURE") == "_T":
    m["default_bundle"]["picks"]["TENURE"] = "TOTD"
if single:
    (D/"all.json.gz").write_bytes(
        gzip.compress(json.dumps(out, separators=(",", ":")).encode(), 6))
else:
    ai = next(i for i, x in enumerate(m["dims"]) if x["id"] == m["area_dim"])
    codes = m["dims"][ai]["ids"]
    from collections import defaultdict
    by = defaultdict(list)
    for r in out: by[codes[r["k"][ai]]].append(r)
    for f in (D/"parts").glob("*.json.gz"): f.unlink()
    parts = {}
    for code, rs in by.items():
        (D/"parts"/f"{code}.json.gz").write_bytes(
            gzip.compress(json.dumps(rs, separators=(",", ":")).encode(), 6))
        parts[code] = {"file": f"{code}.json.gz", "n": sum(len(r["v"]) for r in rs),
                       "bytes": (D/"parts"/f"{code}.json.gz").stat().st_size}
    m["parts"] = parts
(D/"meta.json").write_text(json.dumps(m, separators=(",", ":")))
print(f"zero-year averages removed: {dropped}; series emptied: {emptied}; "
      f"remaining {m['n_obs']:,} observations")
