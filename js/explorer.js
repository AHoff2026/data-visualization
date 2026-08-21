// ---------- dataset explorer: data-aware controls + chart/table views ----------
import { el, clear, fmtNum, periodToNum, debounce } from "./util.js?v=daeb1107";
import { getFlowMeta, getSeries } from "./store.js?v=daeb1107";
import { desiredPicks, seedPicks as sharedSeed } from "./series.js?v=daeb1107";
import { lineChart, smallMultiples, slotVar, SERIES_SLOTS, autosize } from "./chart.js?v=daeb1107";
import { dataTable } from "./table.js?v=daeb1107";
import { editable, textOf } from "./edits.js?v=daeb1107";

const TOTALISH = ["_T", "_Z", "TOT", "T"];

/** Read the view state encoded after "?" in the hash route. */
function readUrlState() {
  const h = location.hash.replace(/^#/, "");
  const q = h.indexOf("?");
  if (q < 0) return {};
  const sp = new URLSearchParams(h.slice(q + 1));
  const out = {};
  if (sp.get("v")) out.view = sp.get("v");
  if (sp.get("sm")) out.smScale = sp.get("sm");
  if (sp.get("bd")) out.breakdown = sp.get("bd");
  if (sp.get("e")) out.entities = sp.get("e").split(" ").filter(Boolean);
  if (sp.get("p")) {
    out.picks = {};
    for (const kv of sp.get("p").split(",")) {
      const i = kv.indexOf(":");
      if (i > 0) out.picks[kv.slice(0, i)] = kv.slice(i + 1);
    }
  }
  return out;
}

export async function renderExplorer(host, slug, catalog) {
  clear(host);
  host.appendChild(el("div", { class: "center-note" },
    el("div", { class: "spinner" }), "Loading dataset…"));

  let meta;
  try { meta = await getFlowMeta(slug); }
  catch (e) { return fatal(host, `Could not load this dataset. ${e.message}`); }

  const SCOPE = `/d/${slug}`;          // key for manual text overrides
  const dims = meta.dims;
  const areaDim = meta.area_dim && dims.some(d => d.id === meta.area_dim) ? meta.area_dim : null;
  const D = dims.length;
  const dimIndex = Object.fromEntries(dims.map((d, i) => [d.id, i]));

  // ============================================================ state
  const ui = {
    breakdown: pickBreakdown(),
    picks: new Array(D).fill(0),   // code index per dimension
    entities: [],                  // code indexes on the breakdown dim
    slots: new Map(),              // entity code index -> colour slot (stable)
    view: "lines",
    smScale: "auto",
    showAll: false,          // tier two of the area list
    notice: null,
  };

  function pickBreakdown() {
    if (areaDim) return areaDim;
    for (const id of (meta.layout_row || []))
      if (id !== meta.time_dim && dimIndex[id] !== undefined && dims[dimIndex[id]].ids.length > 1) return id;
    const multi = dims.filter(d => d.ids.length > 1);
    return (multi.sort((a, b) => b.ids.length - a.ids.length)[0] || dims[0]).id;
  }

  // desired defaults live in series.js, so the home page and the explorer agree
  // ============================================================ load
  let records = [];
  let partial = false;                 // true while only the first-paint bundle is loaded
  async function load(areas, opts) {
    const r = await getSeries(slug, areas, opts);
    records = r.records; partial = r.partial;
  }

  /** Fetch the complete per-area data behind the first paint, then refresh the
   *  controls so availability is exact. The view itself is left alone. */
  async function upgrade() {
    if (!partial) return;
    const ad = areaDim ? dims[dimIndex[areaDim]] : null;
    const areas = ad
      ? (ui.breakdown === areaDim ? ui.entities.map(i => ad.ids[i])
                                  : [ad.ids[ui.picks[dimIndex[areaDim]]]])
      : null;
    try { await load(areas, { allowBundle: false }); }
    catch { return; }
    partial = false;
    state = repair();
    buildControls();
    if (!activeSeries(state.live).length) draw();
  }
  try {
    await load(meta.layout === "parts" && areaDim
      ? preferredAreas(dims[dimIndex[areaDim]], catalog, meta) : null);
  } catch (e) { return fatal(host, `Could not load observations. ${e.message}`); }

  if (!records.length) return fatal(host, "This dataset returned no observations.");

  // ---- seed picks from a REAL record closest to the desired defaults
  seedPicks();
  function seedPicks() {
    const best = sharedSeed(meta, records, dimIndex[ui.breakdown]);
    if (best) ui.picks = best;
  }

  // ============================================================ availability
  /** One pass: live records (match every fixed dim) + per-dim conditional availability. */
  function scan() {
    const bi = dimIndex[ui.breakdown];
    const avail = dims.map(() => new Set());
    const live = [];
    for (const r of records) {
      let miss = 0, missAt = -1;
      for (let i = 0; i < D; i++) {
        if (i === bi) continue;
        if (r.k[i] !== ui.picks[i]) { miss++; missAt = i; if (miss > 1) break; }
      }
      if (miss === 0) {
        live.push(r);
        for (let i = 0; i < D; i++) avail[i].add(r.k[i]);
      } else if (miss === 1) {
        avail[missAt].add(r.k[missAt]);
      }
    }
    return { live, avail };
  }

  /** Make the current picks valid: if nothing matches, adopt the nearest real record. */
  function repair(changedDim = -1) {
    let { live, avail } = scan();
    if (live.length) return { live, avail, repaired: null };
    const bi = dimIndex[ui.breakdown];
    let best = null, bestScore = -1;
    for (const r of records) {
      if (changedDim >= 0 && changedDim !== bi && r.k[changedDim] !== ui.picks[changedDim]) continue;
      let s = 0;
      for (let i = 0; i < D; i++) if (i !== bi && r.k[i] === ui.picks[i]) s++;
      if (s > bestScore) { bestScore = s; best = r; }
    }
    if (!best) {
      if (changedDim >= 0) { // the changed value has no data at all under any combination
        return { live: [], avail: scan().avail, repaired: "none" };
      }
      best = records[0];
    }
    const changes = [];
    for (let i = 0; i < D; i++) {
      if (i === bi || i === changedDim) continue;
      if (best.k[i] !== ui.picks[i]) {
        changes.push(`${dims[i].name} → ${dims[i].names[best.k[i]]}`);
        ui.picks[i] = best.k[i];
      }
    }
    ({ live, avail } = scan());
    return { live, avail, repaired: changes.length ? changes : null };
  }

  // ---- entities: default countries that actually carry data
  function seedEntities(avail) {
    const d = dims[dimIndex[ui.breakdown]];
    const has = avail[dimIndex[ui.breakdown]];
    const ok = i => has.has(i);
    let out = [];
    if (ui.breakdown === areaDim) {
      out = catalog.default_countries
        .map(c => d.ids.indexOf(c)).filter(i => i >= 0 && ok(i));
    }
    if (!out.length) {
      const od = (meta.oecd_defaults || {})[d.id];
      if (od) out = String(od).split("+").map(c => d.ids.indexOf(c)).filter(i => i >= 0 && ok(i));
    }
    if (!out.length) out = [...has].sort((a, b) => a - b).slice(0, 8);
    ui.entities = out;
    reslot();
  }
  /** Stable colour slots: an entity keeps its slot for as long as it stays selected. */
  function reslot() {
    const used = new Set();
    for (const [e, s] of [...ui.slots]) {
      if (!ui.entities.includes(e)) ui.slots.delete(e); else used.add(s);
    }
    ui.entities.forEach((e, pos) => {
      if (ui.slots.has(e)) return;
      let s = 0; while (used.has(s) && s < SERIES_SLOTS) s++;
      if (s < SERIES_SLOTS) { ui.slots.set(e, s); used.add(s); }
      // Past the palette every further series still gets a colour, cycling the
      // slots; the direct label on each line carries identity.
      else ui.slots.set(e, pos % SERIES_SLOTS);
    });
  }

  // ---- apply any state carried in the URL, then validate it against the data
  const urlState = readUrlState();
  if (urlState.view) ui.view = urlState.view;
  if (urlState.smScale) ui.smScale = urlState.smScale;
  if (urlState.breakdown && dimIndex[urlState.breakdown] !== undefined)
    ui.breakdown = urlState.breakdown;
  if (urlState.picks)
    for (const [id, code] of Object.entries(urlState.picks)) {
      const i = dimIndex[id];
      if (i === undefined) continue;
      const j = dims[i].ids.indexOf(code);
      if (j >= 0) ui.picks[i] = j;
    }

  let state = repair();
  if (urlState.entities) {
    const d = dims[dimIndex[ui.breakdown]];
    const has = state.avail[dimIndex[ui.breakdown]];
    const want = urlState.entities.map(c => d.ids.indexOf(c)).filter(i => i >= 0 && has.has(i));
    if (want.length) { ui.entities = want; reslot(); }
    else seedEntities(state.avail);
  } else seedEntities(state.avail);

  // ============================================================ shell
  clear(host);
  host.appendChild(buildHeader());
  const controls = el("div", {});
  const noticeBox = el("div", {});
  const figure = el("section", { class: "figure" });
  const explain = el("div", {});
  host.append(controls, noticeBox, figure, explain);

  function buildHeader() {
    const h = el("header", { style: { marginBottom: "1.25rem" } });
    const topic = topicLabel(catalog, meta.topic);
    const kick = el("p", { class: "kicker" }, textOf(SCOPE, "kicker", topic));
    const title = el("h1", {}, textOf(SCOPE, "title", meta.name));
    editable(kick, SCOPE, "kicker", topic);
    editable(title, SCOPE, "title", meta.name);
    h.appendChild(kick);
    h.appendChild(title);
    if (meta.desc_html) {
      // Show the opening paragraph only; the rest sits behind the button, so
      // every dataset page starts at the same height.
      const chunks = splitParagraphs(meta.desc_html);
      const lead = chunks[0] || "";
      const rest = chunks.slice(1).join("<br>");

      const body = el("div", { class: "standfirst", html: textOf(SCOPE, "desc", lead),
        style: { maxWidth: "44rem" } });
      editable(body, SCOPE, "desc", lead, { plain: false });
      h.appendChild(body);

      if (rest) {
        const more = el("div", { class: "standfirst desc__rest", hidden: true,
          html: textOf(SCOPE, "desc_rest", rest), style: { maxWidth: "44rem" } });
        editable(more, SCOPE, "desc_rest", rest, { plain: false });
        const btn = el("button", { class: "chip", style: { marginTop: ".5rem" },
          onclick: () => {
            more.hidden = !more.hidden;
            btn.textContent = more.hidden ? "Read the full description" : "Show less";
          } }, "Read the full description");
        h.append(more, btn);
      }
    }
    h.appendChild(el("p", { class: "figure__sub", style: { marginTop: ".85rem" } },
      `${meta.n_series.toLocaleString("en-GB")} series · ` +
      `${meta.n_obs.toLocaleString("en-GB")} observations · ` +
      `${meta.periods[0]}–${meta.periods[meta.periods.length - 1]}`));
    return h;
  }

  // ============================================================ series
  function activeSeries(live) {
    const bi = dimIndex[ui.breakdown];
    const d = dims[bi];
    const byEnt = new Map();
    for (const r of live) {
      const e = r.k[bi];
      if (!ui.entities.includes(e)) continue;
      const prev = byEnt.get(e);
      if (!prev || r.t.length > prev.t.length) byEnt.set(e, r);
    }
    const list = [];
    for (const e of ui.entities) {
      const r = byEnt.get(e);
      if (!r) continue;
    // OECD's UNIT_MULT is unreliable: it is 3 ("Thousands") on percentage series
    // in DF_INVPT_I and 0 ("Units") on labour-force counts that are in fact
    // thousands. Their own Data Explorer hides the field. Show the published
    // value unchanged and explain the scale in "How to read this".
      const points = r.t.map((ti, j) => ({
        x: periodToNum(meta.periods[ti]), y: r.v[j], period: meta.periods[ti],
      })).filter(p => Number.isFinite(p.x) && Number.isFinite(p.y));
      if (!points.length) continue;
      const slot = ui.slots.get(e);
      const ctx = slot === undefined || slot < 0;
      list.push({ id: d.ids[e], label: d.names[e] || d.ids[e],
        color: ctx ? "var(--context)" : slotVar(slot), context: ctx, points });
    }
    return list;
  }

  function unitLabel() {
    const i = dimIndex["UNIT_MEASURE"];
    if (i === undefined || ui.breakdown === "UNIT_MEASURE") return "";
    return dims[i].names[ui.picks[i]] || "";
  }

  // ============================================================ draw
  let stopSize = null;
  function draw() {
    const y = window.scrollY;
    const list = activeSeries(state.live);
    const unit = unitLabel();
    const d = dims[dimIndex[ui.breakdown]];

    clear(figure);
    const figTitle = el("div", { class: "figure__title" },
      textOf(SCOPE, "figtitle", meta.name));
    editable(figTitle, SCOPE, "figtitle", meta.name);
    const subOriginal = [unit, describePicks()].filter(Boolean).join("  \u00b7  ") || "\u00a0";
    const figSub = el("div", { class: "figure__sub" }, textOf(SCOPE, "figsub", subOriginal));
    editable(figSub, SCOPE, "figsub", subOriginal);
    figure.appendChild(el("div", { class: "figure__head" }, figTitle, figSub));

    const box = el("div", { style: { minHeight: "400px" } });
    figure.appendChild(box);

    if (!list.length) {
      box.appendChild(el("div", { class: "center-note" },
        el("div", {}, "No series for this combination."),
        el("button", { class: "chip", onclick: () => { seedPicks(); state = repair();
          seedEntities(state.avail); rebuild(); } }, "Reset to a valid selection")));
    } else if (ui.view === "table") {
      dataTable(box, list, { unit, filename: slug });
    } else if (ui.view === "small") {
      const res = smallMultiples(box, list.map((s, i) => ({ ...s,
        color: slotVar(i % SERIES_SLOTS), context: false })),
        { unit, height: 78, scale: ui.smScale });
      if (res.scale)
        box.appendChild(el("p", { class: "figure__sub", style: { marginTop: ".55rem" } },
          res.scale === "own"
            ? "Each panel is on its own vertical scale, with its range printed underneath. "
            : "All panels share one vertical scale, so heights are directly comparable. ",
          el("button", { class: "chip", style: { marginLeft: ".3rem" },
            onclick: () => { ui.smScale = res.scale === "own" ? "shared" : "own";
              buildControls(); draw(); } },
            res.scale === "own" ? "Use one shared scale" : "Give each its own scale")));
    } else {
      if (stopSize) stopSize();
      stopSize = autosize(box, (h) => lineChart(h, list, { height: 400, unit,
        ariaLabel: `${meta.name}. ${unit}. ${list.length} series.` }));
      const coloured = list.filter(s => !s.context);
      if (coloured.length > 1) {
        const lg = el("div", { class: "legend" });
        for (const s of coloured)
          lg.appendChild(el("span", { class: "legend__i" },
            el("span", { class: "dotmark", style: { background: s.color } }), s.label));
        figure.appendChild(lg);
      }
    }

    figure.appendChild(el("div", { class: "figure__foot" },
      el("span", {}, `Showing ${list.length} of ${d.ids.length} · ${plural(d.name)}` +
        (list.length > SERIES_SLOTS
          ? ` · past ${SERIES_SLOTS} series the colours repeat, so read the label at the end of each line`
          : "")),
      el("span", {}, "Source: OECD · ",
        el("a", { href: meta.source_url, target: "_blank", rel: "noopener" },
          `${meta.agency} ${meta.id}`))));

    window.scrollTo({ top: y });
    writeUrlState();
  }

  /** Keep the address bar in step so a configured view can be shared or reloaded. */
  function writeUrlState() {
    const d = dims[dimIndex[ui.breakdown]];
    const sp = new URLSearchParams();
    sp.set("v", ui.view);
    if (ui.smScale !== "auto") sp.set("sm", ui.smScale);
    sp.set("bd", ui.breakdown);
    if (ui.entities.length) sp.set("e", ui.entities.map(i => d.ids[i]).join(" "));
    const picks = dims.map((dd, i) => dd.id === ui.breakdown || dd.ids.length <= 1
      ? null : `${dd.id}:${dd.ids[ui.picks[i]]}`).filter(Boolean);
    if (picks.length) sp.set("p", picks.join(","));
    const next = `#/d/${slug}?${sp.toString()}`;
    if (location.hash !== next) history.replaceState(null, "", next);
  }

  function describePicks() {
    return dims.map((d, i) => ({ d, i }))
      .filter(({ d, i }) => d.id !== ui.breakdown && d.id !== "UNIT_MEASURE" && d.ids.length > 1)
      .map(({ d, i }) => d.names[ui.picks[i]])
      .filter(v => v && !/^(total|not applicable|all|annual)$/i.test(v))
      .slice(0, 5).join("  ·  ");
  }

  function showNotice() {
    clear(noticeBox);
    if (!ui.notice) return;
    noticeBox.appendChild(el("p", {
      style: { fontSize: ".78rem", color: "var(--ink-2)", background: "var(--accent-soft)",
        border: "1px solid var(--rule-strong)", borderRadius: "3px",
        padding: ".45rem .65rem", margin: "0 0 .8rem" } }, ui.notice));
  }

  // ============================================================ controls
  let chipBox = null, chipSearch = null;

  function rebuild() { buildControls(); showNotice(); draw(); buildExplain(); }

  function applyChange(dimIdx, codeIdx) {
    ui.picks[dimIdx] = codeIdx;
    const r = repair(dimIdx);
    state = r;
    if (r.repaired === "none") {
      ui.notice = `“${dims[dimIdx].names[codeIdx]}” has no observations in this dataset under any combination.`;
    } else if (r.repaired) {
      ui.notice = `Adjusted to keep data in view: ${r.repaired.join("; ")}.`;
    } else ui.notice = null;
    // drop entities that no longer have data, keep the rest (and their colours)
    const has = state.avail[dimIndex[ui.breakdown]];
    const kept = ui.entities.filter(e => has.has(e));
    if (kept.length) ui.entities = kept; else seedEntities(state.avail);
    reslot();
    rebuild();
  }

  function buildControls() {
    clear(controls);
    const row1 = el("div", { class: "ctlrow" });

    const seg = el("div", { class: "seg", role: "group", "aria-label": "View" });
    for (const [k, lbl] of [["lines", "Trends"], ["small", "Country snapshots"], ["table", "Table"]])
      seg.appendChild(el("button", { "aria-pressed": String(ui.view === k),
        onclick: () => { ui.view = k; buildControls(); draw(); } }, lbl));
    row1.appendChild(seg);

    const multi = dims.filter(d => d.ids.length > 1);
    if (multi.length > 1) {
      const sel = el("select", { onchange: async (e) => {
        ui.breakdown = e.target.value; ui.slots.clear();
        if (meta.layout === "parts" && areaDim)
          await load(ui.breakdown === areaDim
            ? preferredAreas(dims[dimIndex[areaDim]], catalog, meta) : null,
            { allowBundle: false });
        state = repair(); seedEntities(state.avail); ui.notice = null; rebuild();
      } });
      for (const d of multi)
        sel.appendChild(el("option", { value: d.id, selected: d.id === ui.breakdown },
          `${d.name} (${d.ids.length})`));
      row1.appendChild(el("div", { class: "field" }, el("label", {}, "Compare by"), sel));
    }

    for (let i = 0; i < D; i++) {
      const d = dims[i];
      if (d.id === ui.breakdown || d.ids.length <= 1) continue;
      const has = state.avail[i];
      const sel = el("select", { onchange: (e) => applyChange(i, +e.target.value) });
      d.ids.forEach((code, j) => {
        const ok = has.has(j);
        sel.appendChild(el("option", { value: j, selected: j === ui.picks[i] },
          (d.names[j] || code) + (ok || partial ? "" : "  — no data here")));
      });
      row1.appendChild(el("div", { class: "field" },
        el("label", { title: d.def || "" }, d.name), sel));
    }
    controls.appendChild(row1);

    // ---- entity chips (rebuilt only on structural change; toggles patch in place)
    const d = dims[dimIndex[ui.breakdown]];
    const row2 = el("div", { class: "ctlrow", style: { gap: ".35rem" } });
    chipSearch = el("input", { type: "search",
      placeholder: `Filter ${d.name.toLowerCase()}…`, style: { minWidth: "12rem" } });
    row2.appendChild(chipSearch);
    if (d.id === areaDim) {
      row2.appendChild(el("button", { class: "chip", onclick: async () => {
        const want = catalog.sample_countries || catalog.default_countries;
        ui.entities = want.map(c => d.ids.indexOf(c))
          .filter(i => i >= 0 && state.avail[dimIndex[ui.breakdown]].has(i));
        ui.slots.clear(); reslot(); await maybeReload(); rebuild(); } }, "Sample countries"));
      row2.appendChild(el("button", { class: "chip", "aria-pressed": String(ui.showAll),
        onclick: () => { ui.showAll = !ui.showAll; buildControls(); } },
        ui.showAll ? "Hide additional countries" : "Additional countries"));
    }
    row2.appendChild(el("button", { class: "chip", onclick: () => {
      ui.entities = []; ui.slots.clear(); paintChips(); draw(); } }, "Clear"));
    controls.appendChild(row2);

    chipBox = el("div", { class: "ctlrow",
      style: { gap: ".3rem", maxHeight: "9rem", overflowY: "auto", margin: "0 0 1rem" } });
    controls.appendChild(chipBox);
    chipSearch.addEventListener("input", debounce(paintChips, 120));
    paintChips();
  }

  async function maybeReload() {
    if (meta.layout === "parts" && areaDim && ui.breakdown === areaDim) {
      const d = dims[dimIndex[areaDim]];
      await load(ui.entities.map(i => d.ids[i]), { allowBundle: false });
      state = repair();
    }
  }

  function paintChips() {
    if (!chipBox) return;
    clear(chipBox);
    const d = dims[dimIndex[ui.breakdown]];
    const has = state.avail[dimIndex[ui.breakdown]];
    const q = (chipSearch?.value || "").trim().toLowerCase();
    // Tier one is the short list of areas worth comparing; everything else sits
    // behind "Additional countries" (a search always looks across both).
    const core = (d.id === areaDim && !ui.showAll && !q && catalog.core_areas)
      ? new Set(catalog.core_areas) : null;
    const idxs = d.ids.map((_, i) => i).filter(i =>
      (!q || (d.names[i] || "").toLowerCase().includes(q) || d.ids[i].toLowerCase().includes(q))
      && (!core || core.has(d.ids[i]) || ui.entities.includes(i)));
    const withData = partial ? idxs : idxs.filter(i => has.has(i));
    const shown = withData.slice(0, 400);
    for (const i of shown) chipBox.appendChild(chip(d, i));
    const rest = idxs.length - withData.length;
    if (rest > 0)
      chipBox.appendChild(el("span", { class: "figure__sub", style: { alignSelf: "center" } },
        `${rest} more have no data for this combination`));
    if (core)
      chipBox.appendChild(el("span", { class: "figure__sub", style: { alignSelf: "center" } },
        `${d.ids.length - shown.length} further areas under “Additional countries”`));
  }

  function chip(d, i) {
    const on = ui.entities.includes(i);
    const slot = ui.slots.get(i);
    const c = el("button", { class: "chip", "aria-pressed": String(on),
      title: d.code_defs?.[d.ids[i]] || d.names[i] || d.ids[i],
      onclick: async () => {
        if (ui.entities.includes(i)) ui.entities = ui.entities.filter(x => x !== i);
        else ui.entities = [...ui.entities, i];
        reslot();
        await maybeReload();
        paintChips();      // in place — no layout reflow above the chart
        draw();
      } },
      el("span", { class: "chip__swatch",
        style: { background: on && slot >= 0 ? slotVar(slot) : "var(--context)" } }),
      d.names[i] || d.ids[i]);
    return c;
  }

  // ============================================================ "how to read this"
  function buildExplain() {
    clear(explain);
    const sec = el("section", { style: { marginTop: "2rem", maxWidth: "48rem" } });
    const HEAD = "Details";
    const head = el("h2", { style: { fontSize: "1.15rem", marginBottom: ".6rem" } },
      textOf(SCOPE, "explainhead", HEAD));
    editable(head, SCOPE, "explainhead", HEAD);
    sec.appendChild(head);

    const dl = el("div", { style: { display: "grid", gap: ".55rem" } });
    const unit = unitLabel();
    if (unit) dl.appendChild(explainRow("Unit", unit, null, SCOPE));
    const mi = dimIndex["MEASURE"];
    if (mi !== undefined) dl.appendChild(explainRow("Measure",
      dims[mi].names[ui.picks[mi]], dims[mi].code_defs?.[dims[mi].ids[ui.picks[mi]]], SCOPE));

    for (let i = 0; i < D; i++) {
      const d = dims[i];
      if (d.ids.length <= 1 || d.id === "MEASURE" || d.id === "UNIT_MEASURE") continue;
      if (d.id === areaDim) continue;        // the area chips already show this
      const cur = d.id === ui.breakdown
        ? `${ui.entities.length} selected of ${d.ids.length}`
        : d.names[ui.picks[i]];
      dl.appendChild(explainRow(d.name, cur,
        d.def || (d.id === ui.breakdown ? null : d.code_defs?.[d.ids[ui.picks[i]]]), SCOPE));
    }
    sec.appendChild(dl);

    // a derived unit must never read as an OECD-published figure
    const derivedInfo = (meta.derived_units || {})[dims[dimIndex["UNIT_MEASURE"]]
      ?.ids[ui.picks[dimIndex["UNIT_MEASURE"]]]];
    if (derivedInfo)
      sec.appendChild(el("p", { class: "figure__sub", style: { marginTop: ".9rem",
        borderLeft: "2px solid var(--accent)", paddingLeft: ".6rem" } },
        `Derived, not published by OECD: ${derivedInfo.method}. ` +
        `The denominator is ${derivedInfo.total_code.replace(/\+/g, " + ")} on the ` +
        `${derivedInfo.over.toLowerCase().replace(/_/g, " ")} dimension. ` +
        `OECD publishes this table only as counts of persons, which mostly measures ` +
        `country size; the share is exact arithmetic on their own figures.`));

    if (meta.unit_mult_published === "0" && /person|number|thousand/i.test(unit || ""))
      sec.appendChild(el("p", { class: "figure__sub", style: { marginTop: ".9rem" } },
        "Scale note: OECD publishes this series with a unit multiplier of “Units”, and " +
        "its own Data Explorer hides that field. Values are reproduced exactly as OECD " +
        "supplies them — for labour-force series they are conventionally counts in " +
        "thousands, so read 128.28 as roughly 128,000. Check the source notes before quoting."));

    sec.appendChild(el("p", { class: "figure__sub", style: { marginTop: ".9rem" } },
      "Every figure is taken unmodified from the OECD SDMX API; nothing is imputed, " +
      "smoothed or rebased. ",
      el("a", { href: meta.source_url, target: "_blank", rel: "noopener" },
        "Open this table in the OECD Data Explorer"), "."));
    explain.appendChild(sec);
  }

  function explainRow(term, value, def, scope) {
    return el("div", { style: { borderTop: "1px solid var(--rule)", paddingTop: ".45rem" } },
      el("div", { style: { display: "flex", gap: ".7rem", flexWrap: "wrap", alignItems: "baseline" } },
        el("span", { style: { fontSize: ".625rem", letterSpacing: ".09em",
          textTransform: "uppercase", color: "var(--ink-muted)", fontWeight: "600",
          minWidth: "9rem" } }, term),
        mark(el("span", { style: { fontSize: ".875rem" } }, value || "—"),
          scope, "row:" + term, value || "—")),
      def ? mark(el("p", { class: "figure__sub", style: { margin: ".2rem 0 0 9.7rem" } }, def),
        scope, "def:" + term, def) : null);
  }

  rebuild();
  if (partial) setTimeout(upgrade, 60);
  const onResize = debounce(draw, 180);
  window.addEventListener("resize", onResize);
  host.addEventListener("explorer:teardown",
    () => window.removeEventListener("resize", onResize), { once: true });
}

// ============================================================ helpers
/** Split a description into paragraphs, whatever markup OECD used for them. */
function splitParagraphs(html) {
  let t = String(html || "").trim();
  const parts = t
    .split(/<\/p>\s*|<br>\s*(?:<br>\s*)*/i)
    .map(x => x.replace(/^\s*<p[^>]*>/i, "").trim())
    .filter(Boolean);
  if (parts.length > 1) return parts;
  // one long block: break after the first sentence that ends past 220 chars
  const plain = parts[0] || t;
  const m = /^([\s\S]{220,}?[.!?])\s+(?=[A-Z(])/.exec(plain);
  return m ? [m[1], plain.slice(m[0].length)] : [plain];
}

/** Show any stored override for a field and make the node editable. */
function mark(node, scope, field, original) {
  if (!scope) return node;
  const over = textOf(scope, field, original);
  if (over !== original) node.textContent = over;
  editable(node, scope, field, original);
  return node;
}

function plural(name) {
  const n = String(name).toLowerCase();
  if (/s$/.test(n)) return n;
  if (/(ch|sh|x|z)$/.test(n)) return n + "es";
  if (/[^aeiou]y$/.test(n)) return n.slice(0, -1) + "ies";
  return n + "s";
}
function fatal(host, msg) {
  clear(host);
  host.appendChild(el("div", { class: "center-note" }, msg));
}
function preferredAreas(d, catalog, meta) {
  const parts = Object.keys(meta.parts || {});
  const want = catalog.default_countries.filter(c => parts.includes(c));
  return want.length ? want : parts.slice(0, 12);
}
export function topicLabel(catalog, path) {
  if (!path || !catalog.topic_tree) return "OECD";
  let node = catalog.topic_tree, names = [];
  for (const p of String(path).split(".")) {
    const hit = (node.categories || []).find(c => c.id === p);
    if (!hit) break;
    names.push(hit.name || hit.id); node = hit;
  }
  return names.length ? names.join(" › ") : "OECD";
}
