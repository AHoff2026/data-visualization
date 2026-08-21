# Data Visualization

Independent, fast, interactive charts built directly from the OECD's SDMX
statistical services — 51 datasets, 17,013,594 observations, every country and
every year, reproduced without modification.

**Live site:** https://ahoff2026.github.io/data-visualization/

## How it is built

| Stage | Script | What it does |
|---|---|---|
| Harvest | `scripts/harvest.py` | Pulls every dataflow's full data + structure from `sdmx.oecd.org` |
| Catalog | `scripts/build_catalog.py` | Topic tree, dimensions, codelists |
| Transform | `scripts/transform.py` | CSV → sparse integer-indexed series JSON (8.1 GB → 57 MB, lossless) |
| Labels | `scripts/patch_labels.py` | Resolves human names for dimensions and codes |
| Enrich | `scripts/enrich_meta.py` | Full descriptions, OECD's own default selections, concept definitions |
| Site data | `scripts/build_site_data.py` | Slim catalog + payload placement |

## Verification

- `tests/verify_data.py` — observation-count parity against source, plus an
  exact-value sample per dataset. **51/51 pass, 17,013,594 observations.**
- `tests/verify_site.mjs` — every dataset rendered in WebKit (Safari's engine):
  chart geometry, resolved labels, axis ticks, all three views, tooltip,
  zero console errors. **51/51 pass.**

No framework, no build step, no runtime dependencies. Vanilla ES modules and
hand-rolled SVG. Palette validated for colour-vision deficiency in both themes.

Data © OECD. This site restates it; it does not alter it.
