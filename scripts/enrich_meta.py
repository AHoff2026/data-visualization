#!/usr/bin/env python3
"""Enrich each flow's meta.json from the harvested SDMX structures:
full description, OECD's own DEFAULT selection, hidden dimensions, layout hints,
and concept/code definitions — the material that explains what is being measured."""
import json, pathlib, re, html

ROOT = pathlib.Path.home()/"Documents/data-visualization"
STRUCT, FLOWS = ROOT/"meta/struct", ROOT/"site/data/flows"

ALLOWED = {"p", "br", "a", "em", "strong", "b", "i", "ul", "ol", "li", "sup", "sub"}
# Real HTML tags we recognise. Anything else after "<" is literal text — OECD
# descriptions are full of things like "<1 month" and "< 3 months", which must
# not be swallowed as markup.
KNOWN = ALLOWED | {
    "div", "span", "table", "thead", "tbody", "tr", "td", "th", "img", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6", "font", "small", "big", "u", "s",
    "blockquote", "pre", "code", "script", "style", "html", "body", "head",
    "dl", "dt", "dd", "section", "article", "figure", "figcaption", "nbsp",
}
# A tag body may not cross another "<": otherwise a false start such as
# "<1 year, ..." swallows the real <p /> that follows it.
TAG = re.compile(r'<\s*(/?)\s*([a-zA-Z0-9]+)([^<>]*?)/?\s*>')
HREF = re.compile(r'href\s*=\s*"([^"]*)"|href\s*=\s*\'([^\']*)\'', re.I)

def sanitize(s):
    """Keep a small allowlist of tags; drop everything else. Links get rel/target."""
    if not s: return ""
    out, pos = [], 0
    for m in TAG.finditer(s):
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3) or ""
        if tag not in KNOWN:
            continue                      # leave it in the text, escaped below
        out.append(html.escape(s[pos:m.start()], quote=False))
        pos = m.end()
        if tag not in ALLOWED: continue
        if tag == "br" or (tag == "p" and "/" in m.group(0)[-2:] and not closing):
            out.append("<br>"); continue
        if closing: out.append(f"</{tag}>"); continue
        if tag == "a":
            h = HREF.search(attrs)
            url = (h.group(1) or h.group(2)) if h else ""
            if url.startswith(("http://", "https://")):
                out.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">')
            else:
                out.append("<span>")
        else:
            out.append(f"<{tag}>")
    out.append(html.escape(s[pos:], quote=False))
    txt = "".join(out)
    txt = re.sub(r'(<br>\s*){3,}', '<br><br>', txt)
    # OECD often uses the raw URL as the link text; show the site instead
    def relabel(m):
        inner = m.group(2).strip()
        if not re.match(r'^https?://', inner):
            return m.group(0)
        # OECD often uses the raw URL as the link text. Name the destination
        # from its path instead of showing a bare domain.
        path = re.sub(r'^https?://[^/]+/?', '', inner).rstrip('/')
        seg = path.split('/')[-1] if path else ''
        seg = re.sub(r'\.(htm|html|pdf|aspx?)$', '', seg, flags=re.I)
        seg = re.sub(r'[-_+]+', ' ', seg).strip()
        if len(seg) < 3:
            seg = re.sub(r'^https?://(www\.)?', '', inner).split('/')[0]
        else:
            ACR = {"ictwss","oecd","lfs","pisa","gdp","oda","sdmx","ict","vet",
                   "neet","eag","alfs","socx","ppp","eu","us","uk","stan","tiva"}
            words = []
            for w in seg.split():
                words.append(w.upper() if w.lower() in ACR else w)
            seg = " ".join(words)
            seg = seg[:1].upper() + seg[1:]
        return f'{m.group(1)}{html.escape(seg, quote=False)}</a>'
    txt = re.sub(r'(<a [^>]*>)(.*?)</a>', relabel, txt, flags=re.S)
    return txt.strip()

def parse_kv(title):
    """'SEX=_T,AGE=_T,LASTNPERIODS=10' -> dict"""
    out = {}
    for part in (title or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out

def urn_tail(urn):
    if not urn: return (None, None)
    t = urn.split("=")[-1]
    m = re.match(r'([^:]+):([^(]+)\(([^)]+)\)(?:\.(.+))?$', t)
    return (f"{m.group(1)}:{m.group(2)}", m.group(4)) if m else (None, None)

report = {"flows": 0, "with_defaults": 0, "with_desc": 0, "dim_defs": 0, "code_defs": 0}

for mp in sorted(FLOWS.glob("*/meta.json")):
    slug = mp.parent.name
    sp = STRUCT/f"{slug}.json"
    if not sp.exists(): continue
    d = json.loads(sp.read_text())["data"]
    meta = json.loads(mp.read_text())
    df = d["dataflows"][0]

    ann = {}
    for a in df.get("annotations", []):
        ann.setdefault(a.get("type"), []).append(a.get("title"))

    meta["desc_html"] = sanitize(df.get("description") or "")
    meta["desc_text"] = re.sub(r'<[^>]+>', ' ', df.get("description") or "")
    meta["desc_text"] = re.sub(r'\s+', ' ', meta["desc_text"]).strip()
    if meta["desc_html"]: report["with_desc"] += 1

    defaults = parse_kv((ann.get("DEFAULT") or [""])[0])
    meta["oecd_defaults"] = defaults
    if defaults: report["with_defaults"] += 1
    meta["oecd_hidden"] = parse_kv((ann.get("NOT_DISPLAYED") or [""])[0])
    meta["layout_row"] = [x for x in ((ann.get("LAYOUT_ROW") or [""])[0] or "").split(",") if x]
    meta["layout_section"] = [x for x in ((ann.get("LAYOUT_ROW_SECTION") or [""])[0] or "").split(",") if x]

    # concept definitions
    cdef = {}
    for cs in d.get("conceptSchemes", []):
        for c in cs.get("concepts", []):
            if c.get("description"): cdef[c["id"]] = c["description"]

    # codelists (key -> {code: description})
    cldesc, dim_cl = {}, {}
    for cl in d.get("codelists", []):
        cldesc[f'{cl.get("agencyID")}:{cl["id"]}'] = {
            c["id"]: c["description"] for c in cl.get("codes", []) if c.get("description")}
    comp = d["dataStructures"][0]["dataStructureComponents"]
    for dim in comp["dimensionList"]["dimensions"]:
        k, _ = urn_tail(dim.get("localRepresentation", {}).get("enumeration"))
        if k: dim_cl[dim["id"]] = k

    for dm in meta["dims"]:
        if dm["id"] in cdef:
            dm["def"] = cdef[dm["id"]]; report["dim_defs"] += 1
        src = cldesc.get(dim_cl.get(dm["id"]), {})
        defs = {c: src[c] for c in dm["ids"] if c in src}
        if defs:
            dm["code_defs"] = defs; report["code_defs"] += len(defs)

    # scale caveat: OECD publishes UNIT_MULT but hides it when 0
    meta["unit_mult_published"] = meta.get("oecd_hidden", {}).get("UNIT_MULT")

    mp.write_text(json.dumps(meta, separators=(",", ":")))
    report["flows"] += 1

print(json.dumps(report, indent=1))
