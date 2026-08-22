// ---------- home-page featured charts ----------
import { el, clear } from "./util.js?v=43b83737";
import { editable, textOf } from "./edits.js?v=43b83737";
import { getFlowMeta, getSeries } from "./store.js?v=43b83737";
import { lineChart, autosize } from "./chart.js?v=43b83737";
import { seedPicks, scanRecords, toSeries } from "./series.js?v=43b83737";

/** Small, meaningful, quick-loading series that open the publication. */
export const FEATURED = [
  { slug: "OECD.ELS.SAE__DF_TUD",
    title: "Union membership has fallen almost everywhere",
    note: "Share of employees who belong to a trade union." },
  { slug: "OECD.ELS.SAE__DF_CBC",
    title: "Collective bargaining coverage tells a different story",
    note: "Share of employees covered by a collective agreement — coverage can stay high as membership falls." },
  { slug: "OECD.ELS.SPD__DF_SOCX_AGG",
    title: "What the welfare state actually costs",
    note: "Social expenditure as a share of GDP." },
  { slug: "OECD.ELS.SAE__GENDER_WAGE_GAP",
    title: "The gender wage gap, narrowing slowly",
    note: "Difference between male and female median earnings, as a share of male median earnings." },
];

const HOME_COUNTRIES = 6;   // six lines read cleanly at teaser size

export async function renderFeatured(host, catalog) {
  const grid = el("div", { class: "featgrid" });
  host.appendChild(grid);

  // a card must not outlive its dataset
  const have = new Set((catalog.flows || []).map(x => x.slug));
  const cards = FEATURED.filter(f => have.has(f.slug));

  await Promise.all(cards.map(async (f) => {
    // Each card's headline and note are editable from the landing page.
    const SC = "/featured/" + f.slug;
    const t = el("div", { class: "feat__t" }, textOf(SC, "title", f.title));
    const note = el("div", { class: "figure__sub" }, textOf(SC, "note", f.note));
    editable(t, SC, "title", f.title);
    editable(note, SC, "note", f.note);
    const cell = el("a", { class: "feat", href: `#/d/${f.slug}` }, t, note);
    // in edit mode a click should place the caret, not follow the link
    cell.addEventListener("click", (e) => {
      if (document.documentElement.dataset.editing === "1" &&
          (e.target === t || e.target === note || t.contains(e.target) || note.contains(e.target)))
        e.preventDefault();
    });
    const box = el("div", { style: { marginTop: ".7rem", minHeight: "180px" } });
    cell.appendChild(box);
    grid.appendChild(cell);
    box.appendChild(el("div", { class: "center-note", style: { minHeight: "180px" } },
      el("div", { class: "spinner" })));

    try {
      const meta = await getFlowMeta(f.slug);
      const bi = meta.dims.findIndex(d => d.id === (meta.area_dim || meta.dims[0].id));
      const { records } = await getSeries(f.slug,
        meta.layout === "parts" ? catalog.default_countries : null);
      if (!records.length) throw new Error("no records");
      const picks = seedPicks(meta, records, bi);
      const { live, avail } = scanRecords(meta, records, bi, picks);
      const d = meta.dims[bi];
      const has = avail[bi];
      const ents = catalog.default_countries
        .map(c => d.ids.indexOf(c)).filter(i => i >= 0 && has.has(i))
        .slice(0, HOME_COUNTRIES);
      const list = toSeries(meta, live, bi, ents, (e) => ents.indexOf(e));
      clear(box);
      if (!list.length) throw new Error("no series");
      autosize(box, (h) => lineChart(h, list, { height: 200, directLabels: true,
        showDots: false, ariaLabel: f.title }));
      const last = list[0].points[list[0].points.length - 1];
      cell.appendChild(el("div", { class: "feat__f" },
        el("span", {}, meta.name),
        el("span", {}, `${meta.periods[0]}–${meta.periods[meta.periods.length - 1]}`)));
    } catch (e) {
      clear(box);
      box.appendChild(el("div", { class: "center-note", style: { minHeight: "120px" } },
        "Chart unavailable — open the dataset."));
    }
  }));
}
