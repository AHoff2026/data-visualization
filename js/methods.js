// ---------- methods page ----------
import { el, clear } from "./util.js?v=49b03c63";
import { editable, textOf } from "./edits.js?v=49b03c63";

const S = "/methods";
const T = (field, original) => {
  const n = el("div", {}, textOf(S, field, original));
  return n;
};

/** A section of body text, editable like everything else. */
function para(field, text) {
  const p = el("p", {}, textOf(S, field, text));
  editable(p, S, field, text);
  return p;
}
function head(field, text) {
  const h = el("h2", { style: { margin: "2rem 0 .6rem" } }, textOf(S, field, text));
  editable(h, S, field, text);
  return h;
}

export function renderMethods(host, catalog) {
  clear(host);
  const n = catalog.flows.length;
  const obs = catalog.flows.reduce((a, f) => a + (f.n_obs || 0), 0);

  const kick = el("p", { class: "kicker" }, textOf(S, "kicker", "How this site is built"));
  const h1 = el("h1", {}, textOf(S, "title", "Methods"));
  editable(kick, S, "kicker", "How this site is built");
  editable(h1, S, "title", "Methods");

  const wrap = el("article", { class: "methods" }, kick, h1);

  wrap.appendChild(para("lead",
    `Every figure here comes from the OECD's SDMX statistical services, pulled ` +
    `directly rather than copied from a publication. ${n} datasets, ` +
    `${obs.toLocaleString("en-GB")} observations. Nothing is imputed, smoothed or ` +
    `rebased. Where a number is computed rather than published, the page says so ` +
    `and states the arithmetic.`));

  wrap.appendChild(head("h_units", "Why shares rather than totals"));
  wrap.appendChild(para("p_units",
    "Comparing raw counts across countries mostly measures how big the countries " +
    "are. A dataset therefore opens on a share or a per-capita figure wherever one " +
    "exists, and on a total rather than a sub-category. Counts remain available in " +
    "the Indicator menu for looking at a single country closely."));
  wrap.appendChild(para("p_derived",
    "Five tables published only counts of persons. Four now carry a share computed " +
    "from their own totals, which is exact arithmetic on published figures. The " +
    "fifth, the population outside the labor force, is expressed against OECD's own " +
    "published population for the same country, sex and age band. Derived units are " +
    "labelled as such, the method is stated on the dataset page, and every derived " +
    "value is re-checked against its source before publication."));

  wrap.appendChild(head("h_source", "Where the source is not taken at face value"));
  wrap.appendChild(para("p_mult",
    "OECD's unit multiplier is unreliable. It reads 3, meaning thousands, on " +
    "percentage series in one table, and 0, meaning units, on labour-force counts " +
    "that really are in thousands. Their own Data Explorer hides the field. Values " +
    "here are exactly as published, and the scale is explained where it matters."));
  wrap.appendChild(para("p_transform",
    "The labor force survey tags its rate series as a growth rate. They are levels: " +
    "German unemployment reads 8.1 per cent in 1995 and 3.4 per cent in 2024, " +
    "matching OECD's own published rates. The dial is relabelled and the correction " +
    "is stated on the page."));
  wrap.appendChild(para("p_zeros",
    "A series that is zero at every observation is a gap the source published as a " +
    "figure. Nobody works zero hours for forty years. Where zero cannot be a " +
    "measurement — hours, an index, a currency amount — those series are removed. " +
    "Where a genuine zero is possible, they stay in the data and are kept off the " +
    "chart, with a count under it. Eleven individual observations contradicted " +
    "their own unit, including a satisfaction figure of 68,632,899 per cent; those " +
    "are removed and noted."));

  wrap.appendChild(head("h_dials", "Why there are so few controls"));
  wrap.appendChild(para("p_dials",
    "The source describes each table with up to thirteen dimensions. Most are not " +
    "independent: choosing an indicator often fixes its unit, so two menus would " +
    "produce a grid that is mostly empty. Indicator and unit are therefore one " +
    "control listing only the combinations the data contains. Settings that change " +
    "the number without changing the question — seasonal adjustment, index versus " +
    "level, which questionnaire collected it — sit under Advanced. A control whose " +
    "value is already decided by the rest of the selection is not shown at all."));

  wrap.appendChild(head("h_gaps", "Gaps"));
  wrap.appendChild(para("p_gaps",
    "Where the source does not publish a country, the dataset page names it rather " +
    "than leaving you to discover it by clicking. Some gaps cannot be filled from " +
    "anywhere: OECD publishes average unemployment duration for eighteen areas, and " +
    "Germany, Denmark, Sweden, the Netherlands and the United Kingdom are not among " +
    "them; Eurostat publishes the duration distribution but no average. The same " +
    "question is answered exactly by unemployment by duration, expressed as a share " +
    "of the unemployed."));

  wrap.appendChild(head("h_check", "Checking"));
  wrap.appendChild(para("p_check",
    "The transform is verified against the source by observation count and by an " +
    "exact-value sample per dataset. Every dataset is rendered in WebKit, the engine " +
    "Safari uses, and every control, theme and screen width is exercised. Separate " +
    "checks look for values that contradict their unit, series identical to one " +
    "another, options that repeat a name, and citations that no longer resolve at " +
    "OECD."));

  wrap.appendChild(el("p", { class: "figure__sub", style: { marginTop: "2rem" } },
    "Data © OECD. This site restates it; it does not alter it. ",
    el("a", { href: "https://github.com/AHoff2026/data-visualization",
      target: "_blank", rel: "noopener" }, "Source code and audit scripts"), "."));

  host.appendChild(wrap);
}
