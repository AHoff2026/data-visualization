#!/usr/bin/env python3
"""Move the long tail of each dropdown under a heading, without deleting anything.

Statistical agencies publish a category for every cell of a classification. Most
of those cells are not what anyone came to read: a reader wants "tertiary", not
"short-cycle tertiary general education, sufficient for level completion". The
detail has to stay -- it is why the data is worth having -- but it should not sit
between the reader and the three categories that answer the question.

Every option marked here remains selectable, in a "More detail" group at the foot
of its list. Nothing is removed and no value changes.
"""
import json, gzip, pathlib, collections, re

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"
THRESHOLD = 0.5           # per cent of a dataset's observations

# Options that stay at the top whatever their size: the totals and the headline
# splits a reader starts from.
ALWAYS_PRIMARY = re.compile(r"^(_T|_Z|T|TOTAL)$")

# Curated demotions where a share rule cannot see the hierarchy.
CURATED = {
    # keep the months where benefits actually expire; the rest is a smooth curve
    ("OECD.ELS.JAI__DF_NRR", "UNEMP_DURATION"): {
        "keep": {f"M{n}" for n in
                 [1,2,3,4,6,7,8,9,10,11,12,13,15,19,24,25,31,36,37,55,60]}},
    # three-way split plus the general/vocational cut; ISCED sub-levels demoted
    ("OECD.EDU.IMEP__DF_LSO_NEAC_INAC_MIGR", "ATTAINMENT_LEV"): {
        "keep": {"_T","ISCED11A_0T2","ISCED11A_3_4","ISCED11A_5T8",
                 "ISCED11A_34_44","ISCED11A_35_45","ISCED11A_6T8"}},
    ("OECD.EDU.IMEP__DF_LSO_NEAC_UNEMP_MIGR", "ATTAINMENT_LEV"): {
        "keep": {"_T","ISCED11A_0T2","ISCED11A_3_4","ISCED11A_5T8",
                 "ISCED11A_34_44","ISCED11A_35_45","ISCED11A_6T8"}},
    # total, business economy and the main sectors; 2-digit NACE demoted
    ("OECD.SDD.TPS__DF_PDB", "ACTIVITY"): {
        "keep": {"_T","BTNXL","GTNXL","BTE","C","F","GTI","J","K","L","M_N","OTQ","RTU"}},
    ("OECD.SDD.NAD__DF_TABLE9A", "ACTIVITY"): {"maxlen": 1},
    ("OECD.SDD.NAD__DF_TABLE5_T501", "EXPENDITURE"): {"maxlen": 4},
}

# Dials where the share rule misreads the content. ICTWSS is kept whole by
# request. The others are curated lists whose categories are uneven by nature:
# a small category there is a deliberate distinction, not a long tail.
EXEMPT_SLUGS = {"OECD_AIAS__ICTWSS"}
EXEMPT_DIALS = {("ESTAT__DF_INWORK_POV", "BREAKDOWN"),
                ("ESTAT__DF_DEPRIVATION", "ITEM"),
                ("OWID__LABOR_SHARE", "MEASURE"),
                ("WID_LIS__DF_CONCENTRATION", "MEASURE")}

def load(d, m):
    if m["layout"] == "single":
        f = d/"all.json.gz"
        return json.loads(gzip.decompress(f.read_bytes())) if f.exists() else []
    out = []
    for f in sorted((d/"parts").glob("*.json.gz")):
        out += json.loads(gzip.decompress(f.read_bytes()))
    return out

tot_demoted = tot_dials = 0
report = []
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text()); recs = load(mp.parent, meta)
    if not recs: continue
    total = sum(len(r["v"]) for r in recs)
    hidden = set((meta.get("hidden_dims") or {}).keys())
    changed = False
    for i, d in enumerate(meta["dims"]):
        if d["id"] in ("REF_AREA", "UNIT_MEASURE") or d["id"] in hidden: continue
        if meta["slug"] in EXEMPT_SLUGS or (meta["slug"], d["id"]) in EXEMPT_DIALS:
            if d.pop("secondary", None) is not None:
                d.pop("secondary_label", None); changed = True
            continue
        if len(d["ids"]) < 15: 
            if d.pop("secondary", None) is not None: changed = True
            continue
        c = collections.Counter()
        for r in recs: c[r["k"][i]] += len(r["v"])
        rule = CURATED.get((meta["slug"], d["id"]))
        minor = []
        for j, code in enumerate(d["ids"]):
            if ALWAYS_PRIMARY.match(code): continue
            if j == d.get("default"): continue
            if rule and "keep" in rule:
                if code not in rule["keep"]: minor.append(j)
            elif rule and "maxlen" in rule:
                if len(code.strip("_")) > rule["maxlen"]: minor.append(j)
            elif total and c[j]/total*100 < THRESHOLD:
                minor.append(j)
        # a dial must keep a real choice at the top
        if len(d["ids"]) - len(minor) < 3: minor = minor[:max(0, len(d["ids"]) - 3)]
        old = d.get("secondary")
        if minor:
            d["secondary"] = sorted(minor)
            d["secondary_label"] = "More detail"
        else:
            d.pop("secondary", None); d.pop("secondary_label", None)
        if d.get("secondary") != old:
            changed = True
        if minor:
            tot_demoted += len(minor); tot_dials += 1
            report.append((meta["name"], d["name"], len(d["ids"]),
                           len(d["ids"]) - len(minor), len(minor)))
    if changed: mp.write_text(json.dumps(meta, separators=(",", ":")))

report.sort(key=lambda r: -r[4])
print(f'{"dataset":40}{"dial":26}{"was":>5}{"top":>5}{"under More detail":>19}')
for n, dn, was, top, mn in report:
    print(f'  {n[:38]:40}{dn[:24]:26}{was:>5}{top:>5}{mn:>19}')
print(f'\n{tot_demoted} options moved under "More detail" across {tot_dials} dials. '
      f'Nothing removed.')
