#!/usr/bin/env python3
"""Keep source notes to what the reader needs, and cut what only concerns the build.

A note earns its place if it tells the reader what the number means: how the
source defines it, what it covers, which way a scale runs, what the denominator
is. It does not earn its place by describing work done to build the page --
tables merged, rows dropped, units collapsed, defaults chosen -- or by steering
the reader to another table, or by defending a figure that looks surprising.

Rules are data so this can be re-run after any rebuild.
"""
import json, pathlib, re

FLOWS = pathlib.Path.home()/"Documents/data-visualization/site/data/flows"

# a note matching any of these is build housekeeping and goes entirely
DROP = [
    r"^Removed from this table",
    r"observations? removed as impossible for the stated unit",
    r"OECD ships the unit of measure as 'Factor of decile",
    r"OECD ships a second measure in this table",
    r"^OECD also publishes .{0,400}folded in rather than listed twice",
    r"^Four OECD tables are merged here",
    r"single category is always selected",
    r"no combined total for",
    r"^OECD does not publish the incidence of high pay",
]
# a note is cut at the first marker that appears in it
TRIM = [
    "They are not comparable with the earnings dispersion table",
    "The United States reads 4.7 on the 90th-to-10th ratio",
    "That is a fact about their industrial relations",
    "It cannot honestly be derived from the duration distribution",
    "The regular round is shown by default",
    "For employment and participation use the",
    "merged into this dataset rather than kept separate",
    "For citizenship and country of birth only the current EU27",
    "The rest are omitted rather than shown as unlabelled codes",
    "Those are dropped rather than plotted",
    "The dial is relabel",
    "so they are one dataset rather than four near-duplicates",
]
# whole-note replacements where the fact is worth keeping but the framing is not
REWRITE = {
    r"Denmark's employee social security contribution reads 0\.00 per cent":
        "Denmark funds its welfare state through income tax rather than payroll "
        "contributions. Employee social security contributions are zero and employer "
        "contributions are well under one per cent of the wage; the 8 per cent "
        "arbejdsmarkedsbidrag is levied and recorded as an income tax.",
    r"Labor share slightly above 100 per cent for the bottom half":
        "Labor share above 100 per cent for the bottom half of the United States "
        "distribution reflects negative net capital income: in those years the group "
        "paid more interest on debt than it received in capital income, so labor "
        "income exceeded total income.",
    r"'Making ends meet with difficulty' adds Eurostat's two hardest categories":
        "'Making ends meet with difficulty' combines Eurostat's two hardest response "
        "categories, with difficulty and with great difficulty, out of six.",
}

def collapse_sources(n):
    """'Not an OECD table. A - X; B - Y; C - X, via Z.' names each source once."""
    if not n.startswith("Not an OECD table."): return n
    body = n[len("Not an OECD table."):].strip()
    tail = ""
    m = re.search(r",\s*((?:via|assembled and harmonised by)[^.]+)\.", body)
    if m: tail = m.group(1); body = body[:m.start()]
    parts = [x.strip() for x in body.split(";") if "\u2014" in x or " - " in x]
    if len(parts) < 3: return n
    srcs, seen = [], set()
    for x in parts:
        src = re.split(r"\s*(?:\u2014| - )\s*", x)[-1].strip(" .,")
        src = re.sub(r",?\s*(?:via|assembled and harmonised by).*$", "", src).strip(" .,")
        if src and src not in seen: seen.add(src); srcs.append(src)
    if not srcs: return n
    lst = (", ".join(srcs[:-1]) + ", and " + srcs[-1]) if len(srcs) > 1 else srcs[0]
    rest = n[n.find(".", 0) + 1:]
    extra = ""
    k = rest.find("Only observed values")
    if k >= 0: extra = " " + rest[k:].strip()
    return f"Not an OECD table. Sources: {lst}" + (f", {tail}" if tail else "") + "." + extra

def dashes(s):
    """Dashes out. Paired ones become parentheses, single ones a colon."""
    s = re.sub(r"\s+--\s+", " \u2014 ", s)
    # paired: two dashes in one sentence wrap an aside
    def pair(m): return f" ({m.group(1)}) "
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\s\u2014\s([^\u2014.]{3,90}?)\s\u2014\s", pair, s, count=1)
    s = re.sub(r"\s\u2014\s", ": ", s)          # single dash joins a clause
    s = re.sub(r"\s*\(\s*", " (", s)
    s = re.sub(r"\s*\)\s*", ") ", s)
    return re.sub(r"\s+", " ", s).strip()

def tidy(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([.;,:])", r"\1", s)
    s = re.sub(r"[;,]\s*$", ".", s)
    if s and not s.endswith("."): s += "."
    return s

dropped = trimmed = rewritten = 0
for mp in sorted(FLOWS.glob("*/meta.json")):
    meta = json.loads(mp.read_text())
    notes = meta.get("source_notes") or []
    out, seen = [], set()
    for n in notes:
        if any(re.search(p, n) for p in DROP):
            dropped += 1; continue
        for pat, rep in REWRITE.items():
            if re.search(pat, n):
                n = rep; rewritten += 1; break
        else:
            for mark in TRIM:
                i = n.find(mark)
                if i > 0:
                    n = tidy(n[:i]); trimmed += 1; break
        n = dashes(collapse_sources(n))
        n = tidy(n)
        if not n or n in seen: continue     # the same note was baked twice in places
        seen.add(n); out.append(n)
    if out != notes:
        meta["source_notes"] = out
        mp.write_text(json.dumps(meta, separators=(",", ":")))
print(f"notes dropped {dropped}, trimmed {trimmed}, rewritten {rewritten}")
tot = sum(len(json.loads(p.read_text()).get("source_notes") or [])
          for p in FLOWS.glob("*/meta.json"))
print(f"source notes remaining: {tot}")
