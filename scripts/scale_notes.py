#!/usr/bin/env python3
"""State which way an ordinal scale runs.

A chart of a 0-to-6 index is unreadable unless you know whether 6 is more
protection or less. These directions are documented by the sources; they are
recorded here so a rebuild does not lose them.
"""
import json, pathlib

ROOT = pathlib.Path.home()/"Documents/data-visualization"
FLOWS = ROOT/"site/data/flows"

NOTES = {
 "OECD.ELS.JAI__DF_EPL":
   "The scale runs 0 to 6 and higher means stricter: 0 is the least restrictive "
   "regulation of dismissal or of temporary contracts, 6 the most. It scores the "
   "rules as written rather than how they are enforced, and OECD publishes four "
   "methodology versions covering different periods — comparisons across versions "
   "are not like for like.",
 "OECD.ELS.JAI__DF_SBE":
   "The scale runs 1 to 5 and higher means stricter: 5 is the most demanding set of "
   "availability, job-search and sanction requirements placed on benefit recipients.",
 "OWID__LABOR_RIGHTS":
   "Higher means worse. The indicator counts violations of freedom of association "
   "and collective bargaining rights in law and in practice, so 0 is full compliance "
   "and a rising line is a deteriorating one.",
 "OECD.ELS.SPD__DF_PRR":
   "A replacement rate is pension income as a share of earnings before retirement, "
   "so higher means a pension that replaces more of what the job paid.",
 "OECD.ELS.JAI__DF_NRR":
   "A replacement rate is benefit income as a share of previous earnings, so higher "
   "means a benefit that replaces more of the lost wage. These are modelled figures "
   "for specified household types rather than observed averages.",
}
n = 0
for slug, note in NOTES.items():
    mp = FLOWS/slug/"meta.json"
    if not mp.exists(): continue
    m = json.loads(mp.read_text())
    notes = m.setdefault("source_notes", [])
    if note not in notes:
        notes.append(note)
        mp.write_text(json.dumps(m, separators=(",", ":")))
        n += 1
print(f"scale directions recorded: {n}")
