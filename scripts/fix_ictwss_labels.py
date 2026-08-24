#!/usr/bin/env python3
"""Give the ICTWSS indicators labels a dropdown can show.

The codebook runs a variable's short title straight into its full definition with
no delimiter, and in places into the *next* variable's entry, so labels built from
it came out 140 characters long, cut mid-word, and occasionally carrying a second
variable's name. The full definition belongs in the tooltip; the label should be
the name of the thing.

Idempotent, so it can run after any rebuild.
"""
import json, re, pathlib, glob

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"

# Codes whose codebook entry is a question or a lowercase fragment get a written name.
EXPLICIT = {
    "MW_type": "Minimum wage: single or differentiated rates",
    "MW_uprate": "Minimum wage: how changes are decided",
    "MW_comm": "Minimum wage: standing commission",
    "CA_national": "Agreement in force: national or cross-sectoral",
    "CA_sectoral": "Agreement in force: sector",
    "CA_company": "Agreement in force: company or plant",
    "CA_subnational": "Agreement in force: region",
    "CA_occupation": "Agreement in force: occupation",
    "Level": "Predominant bargaining level",
    "Multilevel": "Combination of bargaining levels",
    "Central": "Centralization of bargaining",
    "rAEB": "Reach of additional enterprise bargaining",
    "Art": "Articulation of enterprise bargaining",
    "DR": "Derogation from the law",
    "FAV": "Favourability principle",
    "WSSA": "Wage setting in sectoral agreements",
    "OCG": "Opening clauses in sectoral agreements",
    "OCT": "Crisis-related temporary opening clauses",
    "Index": "Price indexation clauses",
    "Length": "Length of collective agreements",
    "Ext": "Mandatory extension to non-organized employers",
    "Coord": "Coordination of wage setting",
    "Type": "Type of wage coordination",
    "Govint": "Government intervention in bargaining",
    "Peace": "Peace obligation in agreements",
    "CoR": "Procedures for conflicts of rights",
    "CoI": "Procedures for conflicts of interest",
    "SPA_negot": "Social pact under negotiation",
    "TC": "Tripartite council exists",
    "BC": "Bipartite council exists",
    "WC": "Works council: status",
    "WC_type": "Works council: type",
    "WC_struct": "Works council: structure of representation",
    "WC_rights": "Works council: rights",
    "WC_negot": "Works council: negotiation rights",
    "UWRep": "Union workplace representation",
    "TUM_excl": "Union members not in employment, share of membership",
    "UD_hist": "Union density, historical series",
    "SAL": "Employees, total",
    "SAL_female": "Employees, women",
    "SAL_public": "Employees, public sector",
    "Wstat": "Employees covered by statutory wage regulation",
    "NMW": "Statutory minimum wage exists",
    "NCBs": "Collective agreements in force",
    "NCBs_new": "Collective agreements newly concluded or renewed",
}
FAMILY = {
    "UD": "Union density", "UM": "Share of union members",
    "TUM": "Total union membership", "NUM": "Net union membership",
    "SAL": "Employees", "ED": "Employer organization density",
    "NECFs": "Employer confederations", "NUCFs": "Union confederations",
    "NTUs": "Individual trade unions", "NCBs": "Collective agreements concluded",
    "CA": "Cross-sectoral agreement in force", "WC": "Works council status",
    "MW": "Statutory minimum wage", "NMW": "Statutory minimum wage exists",
    "Cov": "Employees covered by collective agreement",
    "UnadjCov": "Bargaining coverage, unadjusted",
    "AdjCov": "Bargaining coverage, adjusted",
    "AdjCov_hist": "Bargaining coverage, adjusted, full historical series",
    "UnadjCov_hist": "Bargaining coverage, unadjusted, full historical series",
    "UD_hist": "Union density, full historical series",
    "Wstat": "Covered by statutory wage setting",
    "RA": "Right of association", "RCB": "Right of collective bargaining",
    "RS": "Right to strike", "SPA": "Social pact",
}
SUFFIX = [("_male","men"),("_female","women"),("_public","public sector"),
    ("_private","private sector"),("_parttime","part-time workers"),
    ("_fulltime","full-time workers"),("_temp","temporary contracts"),
    ("_perm","permanent contracts"),("_age1524","aged 15 to 24"),
    ("_age2554","aged 25 to 54"),("_age5564","aged 55 to 64"),
    ("_ageGE65","aged 65 and over"),("_age1529","aged 15 to 29"),
    ("_age3049","aged 30 to 49"),("_age5064","aged 50 to 64"),
    ("_m","market sector"),("_g","government sector"),
    ("_national","national level"),("_negot","under negotiation"),("_new","new")]

def short(text, cap=64):
    """First clause of a codebook entry, cut on a word boundary."""
    t = re.sub(r"\s+", " ", text or "").strip()
    m = re.match(r"^(.{10,%d}?)(?:[.?]|\s+(?:Proportion|Incidence|Number|Total sum|"
                 r"Trade \(labor\)|Employer organi[sz]ation|Is there|Are there)\b)" % cap, t)
    if m: return m.group(1).strip(" ,;:")
    if len(t) <= cap: return t.rstrip(" .")
    return t[:cap].rsplit(" ", 1)[0].rstrip(" ,;:")

# The codebook runs some scale keys together, so one code's gloss is swallowed
# into the previous entry and the code itself never gets one. Repaired by hand
# against the published ICTWSS codebook.
VALUE_KEY_FIX = {
    "UWRep": {
        "0": "no, or only exceptionally",
        "1": "yes, but only where unions are recognised and have negotiated an agreement",
    },
    "Coord": {
        "4": "wage norms set by one-off central agreements, or by pattern bargaining "
             "with a dominant leader",
    },
}

def main():
    paths = [p for p in glob.glob(str(FLOWS/"*/meta.json"))
             if "ICTWSS" in json.loads(open(p).read()).get("name", "")]
    if not paths: print("ICTWSS dataset not present"); return
    mp = pathlib.Path(paths[0]); meta = json.loads(mp.read_text())
    dim = next(d for d in meta["dims"] if d["id"] == "MEASURE")
    codes = list(dim["ids"]); cd = dim.get("code_defs", {}) or {}
    others = sorted(codes, key=len, reverse=True)

    fixed_defs = 0
    for c in codes:
        t = cd.get(c) or ""
        # a run-on into the next variable's entry: cut at the first other code
        for o in others:
            if o == c: continue
            m = re.search(rf"(?<![A-Za-z0-9_]){re.escape(o)}\s+[A-Z]", t)
            if m and m.start() > 12:
                t = t[:m.start()].strip(); fixed_defs += 1; break
        t = re.sub(r"\bunion\.\s+members\b", "union members", t)
        t = re.sub(r"\s+", " ", t).strip().rstrip(".") 
        if t: cd[c] = t + "."

    names = []
    for c in codes:
        base = re.split(r"_", c)[0]
        head = EXPLICIT.get(c) or FAMILY.get(c) or FAMILY.get(base) or short(cd.get(c) or c)
        head = head[0].upper() + head[1:] if head else head
        bits = [w for suf, w in SUFFIX if c.endswith(suf) or f"{suf}_" in c]
        if c.endswith("_s") or "_s_" in c: bits.append("survey-based")
        # drop qualifiers already carried by the family label
        bits = [b for b in bits if b.lower() not in head.lower()]
        names.append(f"{head}, {', '.join(bits)}" if bits else head)

    seen = {}
    for i, n in enumerate(names):
        if n in seen: names[i] = f"{n} [{codes[i]}]"
        seen[n] = codes[i]

    vd = dim.get("value_defs") or {}
    for code, fixes in VALUE_KEY_FIX.items():
        if code in vd:
            vd[code].update(fixes)
    dim["value_defs"] = vd
    dim["names"] = names; dim["code_defs"] = cd
    mp.write_text(json.dumps(meta, separators=(",", ":")))
    ln = [len(n) for n in names]
    print(f"labels rewritten: {len(names)}   spliced definitions repaired: {fixed_defs}")
    print(f"label length now: min {min(ln)} median {sorted(ln)[len(ln)//2]} max {max(ln)}")
    for c, n in list(zip(codes, names))[:8]: print(f"   {c:16} {n}")

main()
