# Overnight bug list (from Alex, 2026-08-21 ~01:00)

| # | Report | Root cause hypothesis | Status |
|---|--------|----------------------|--------|
| B1 | Some datasets' visualisations don't work | TBD — full WebKit run | open |
| B2 | Toggling a country scrolls the page up | chip list + figure rebuilt on every toggle → layout jump | open |
| B3 | Newly toggled country not highlighted/labelled | slot assigned by position in list; >8 falls to grey context, no label | open |
| B4 | Dataset summaries broken/cut off (e.g. Unemployment by duration) | description truncated at 420 chars + 600-char catalog cap | open |
| B5 | Unclear what is measured; sub-variables indistinguishable | no concept/measure definitions surfaced; unit not prominent | open |
| B6 | Switzerland ~250 unemployed — units look wrong | UNIT_MULT handling; verify against source | open |
| B7 | "Part-time employment" → "No observations for this selection" | dimension selectors are independent; invalid intersections | open |

## Acceptance bar
Every dataset, on load and after any single control change, must either show a
chart with real geometry or explain precisely why no data exists — never a bare
dead end. Units must match the source. Labels must be human. No console errors
in WebKit. No layout jump on toggle.
