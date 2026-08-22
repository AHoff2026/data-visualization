# Forest and the Trees

Independent, fast, interactive charts built from the OECD's statistical
services — **42 datasets, 16,002,012 observations**, every country and every
year, reproduced without alteration and audited before publication.

**Live:** https://ahoff2026.github.io/data-visualization/

No framework, no build step, no runtime dependencies: vanilla ES modules and
hand-rolled SVG. A dataset's first paint is a single request.

## What the interface is for

Cross-country comparison of raw counts mostly measures country size, so a
dataset opens on a share or a per-capita figure wherever one exists, and on a
total rather than a sub-category. Dials that change the number without changing
the question — seasonal adjustment, index versus level, which questionnaire
collected it — sit under **Advanced**. A dial with one reachable value is
hidden, because the rest of the selection has already decided it. Indicator and
unit are one axis, not two, so they are one menu listing only combinations the
data contains.

A single-year cross-section opens as a ranking, not a time series. Dragging
across a Trends chart zooms the period. The address bar carries the whole view.

## Pipeline

| Stage | Script |
|---|---|
| Harvest | `scripts/harvest.py` — full data and structure per dataflow |
| Catalog | `scripts/build_catalog.py` — OECD's topic tree, dimensions, codelists |
| Transform | `scripts/transform.py` — CSV to sparse integer-indexed series (8.1 GB → 53 MB, lossless) |
| Labels | `scripts/patch_labels.py`, `scripts/clarify_codes.py`, `scripts/qualify_codes.py` |
| Enrich | `scripts/enrich_meta.py` — descriptions, OECD defaults, concept definitions |
| Derive | `scripts/derive_shares.py`, `scripts/derive_percapita.py` |
| Clean | `scripts/clean_impossible.py` — values that contradict their unit |
| Classify | `scripts/classify_dims.py` — which dials earn a place |
| Publish | `scripts/build_default_bundles.py`, `scripts/coverage.py`, `scripts/stamp.py`, `scripts/deploy.sh` |

## Verification

```bash
python3 tests/verify_integrity.py     # every internal reference resolves
python3 tests/verify_derived.py       # derived values against their sources
python3 tests/verify_ranges.py        # values that contradict their unit
python3 tests/verify_duplicates.py    # series identical to one another
python3 tests/verify_zeros.py         # "not reported" published as zero
python3 tests/verify_provenance.py    # datasets still exist at OECD
node tests/verify_units.mjs           # pure chart functions
node tests/verify_site.mjs            # every dataset renders, in WebKit
node tests/verify_deep.mjs            # every control, theme, width, zoom, URL
node tests/verify_a11y.mjs            # labelling, headings, keyboard
```

Audits that inform editorial decisions rather than gate a build:
`scripts/audit_dims.py` (dial pairs that are not independent),
`scripts/audit_crossdup.py` (content duplicated across datasets),
`tests/audit_default_view.mjs`, `tests/audit_defaults.mjs`,
`tests/audit_clutter.mjs`, `tests/verify_breaks.py`.

Tests run in WebKit, the engine Safari uses.

## Where the data is not taken at face value

- OECD's `UNIT_MULT` is unreliable — 3 ("Thousands") on percentage series, 0
  ("Units") on labour-force counts that really are thousands. Values are shown
  exactly as published and the scale is explained on the page.
- The labour force survey's rate series are tagged "Growth rate, period on
  period" but are levels; Germany reads 8.1% in 1995 and 3.4% in 2024, matching
  OECD's published rates. Relabelled, with the correction stated.
- 22 datasets contain series that are zero at every observation. That is "not
  reported" published as data; those series stay off the charts and are counted.
- 11 observations contradict their own unit, including a satisfaction figure of
  68,632,899 per cent. Removed and stated.
- Eight datasets were wholly contained in others and were folded in; each
  survivor names what it absorbed.

Data © OECD. This site restates it; it does not alter it.
