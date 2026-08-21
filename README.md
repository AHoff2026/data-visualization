# Data Visualization

Independent, fast, interactive charts built directly from the OECD's SDMX
statistical services — **51 datasets, 17,013,594 observations**, every country
and every year, reproduced without modification.

**Live:** https://ahoff2026.github.io/data-visualization/

No framework, no build step, no runtime dependencies: vanilla ES modules and
hand-rolled SVG. The whole payload is 57 MB of pre-indexed data; a dataset's
first paint is a single request.

## Pipeline

| Stage | Script | What it does |
|---|---|---|
| Harvest | `scripts/harvest.py` | Every dataflow's full data + structure from `sdmx.oecd.org` |
| Catalog | `scripts/build_catalog.py` | OECD's own topic tree, dimensions, codelists |
| Transform | `scripts/transform.py` | CSV → sparse integer-indexed series (8.1 GB → 57 MB, lossless) |
| Labels | `scripts/patch_labels.py` | Human names for every dimension and code |
| Enrich | `scripts/enrich_meta.py` | Full descriptions, OECD's DEFAULT selections, concept definitions |
| Bundles | `scripts/build_default_bundles.py` | One-request first paint for partitioned datasets |
| Site data | `scripts/build_site_data.py` | Slim catalog + payload placement |
| Deploy | `scripts/deploy.sh` | Tests, then publishes to Pages; refuses a failing build |

## Design decisions worth knowing

- **Nothing is altered.** Values are exactly as OECD publishes them. Where OECD's
  own metadata is misleading — labour-force counts carry a unit multiplier of
  "Units" although they are conventionally thousands — the dataset page says so
  rather than silently rescaling.
- **Controls are data-aware.** Selections seed from OECD's own `DEFAULT`
  annotation, options that hold no data are marked, and a choice that would empty
  the chart repairs the other dimensions and tells you what it changed.
- **Colour never carries identity alone.** The palette holds eight
  colour-vision-safe slots, validated in both themes against the actual page
  surfaces. Beyond eight, series are drawn in grey and labelled directly on the
  chart.
- **Small multiples scale honestly.** Panels share a scale when that is
  comparable, and take their own when a shared one would flatten the small
  panels into straight lines; the range is printed under each.
- **Views are shareable.** The address bar carries the full view state.

## Verification

```bash
node tests/verify_units.mjs    # pure chart functions
node tests/verify_site.mjs     # every dataset renders, in WebKit
node tests/verify_deep.mjs     # every control, theme and width
python3 tests/verify_data.py   # parity against source (needs raw/, re-harvest first)
```

| Suite | Scope | Result |
|---|---|---|
| Data | Observation-count parity + exact-value sample per dataset | **51/51, 17,013,594 observations** |
| Site | Chart geometry, labels, axes, three views, tooltip, zero console errors | **51/51** |
| Deep | Every dimension option, compare-by, entity toggle, URL round-trip, dark theme, mobile | **51/51, ~1,200 interactions** |
| Units | Axis formatting, tick generation, period parsing, number safety | **36/36** |

Tests run in WebKit — the engine Safari uses.

Data © OECD. This site restates it; it does not alter it.
