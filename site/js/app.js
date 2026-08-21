// ---------- router + pages ----------
import { el, clear, $, $$, debounce, slugify } from "./util.js?v=82f6a282";
import { getCatalog } from "./store.js?v=82f6a282";
import { renderExplorer, topicLabel } from "./explorer.js?v=82f6a282";
import { renderFeatured } from "./featured.js?v=82f6a282";
import { setEditing, isEditing, editCount, exportEdits, resetScope, editable, textOf, loadBaked }
  from "./edits.js?v=82f6a282";

let CAT = null;
const main = () => document.getElementById("main");
const rail = () => document.getElementById("rail");

// ---------- theme ----------
function initTheme() {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.dataset.theme = saved;
  const btn = document.getElementById("themebtn");
  const paint = () => {
    const dark = document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme &&
        matchMedia("(prefers-color-scheme: dark)").matches);
    btn.innerHTML = dark
      ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
      : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
    btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
  };
  btn.addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme &&
        matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "light" : "dark";
    localStorage.setItem("theme", dark ? "light" : "dark");
    paint();
    window.dispatchEvent(new Event("resize"));
  });
  paint();
}

// ---------- topic tree helpers ----------
function topTopics() {
  const groups = new Map();
  for (const f of CAT.flows) {
    const top = String(f.topic || "OTHER").split(".")[0];
    if (!groups.has(top)) groups.set(top, []);
    groups.get(top).push(f);
  }
  return [...groups.entries()]
    .map(([code, flows]) => ({ code, flows, name: topicName(code) }))
    .sort((a, b) => b.flows.length - a.flows.length);
}
function topicName(code) {
  const hit = (CAT.topic_tree?.categories || []).find(c => c.id === code);
  return hit ? (hit.name || code) : code;
}
function subGroups(flows) {
  const m = new Map();
  for (const f of flows) {
    const path = String(f.topic || "");
    const key = path.split(".").slice(0, 2).join(".") || path;
    if (!m.has(key)) m.set(key, []);
    m.get(key).push(f);
  }
  return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
}

// ---------- rail ----------
function buildRail(activeSlug) {
  const r = rail(); clear(r);
  const search = el("input", { type: "search", placeholder: "Search datasets…",
    style: { width: "100%", maxWidth: "none", marginBottom: "1rem" },
    "aria-label": "Search datasets" });
  const list = el("nav", { "aria-label": "Datasets" });

  let showAll = false;
  const paint = () => {
    clear(list);
    const q = search.value.trim().toLowerCase();
    const groups = topTopics();
    // Featured datasets carry the research; the rest sit behind a toggle so the
    // menu reads as a publication rather than a database dump. Search always
    // looks across both.
    const anyFeatured = CAT.flows.some(f => f.featured);
    for (const g of groups) {
      const flows = g.flows.filter(f => (!q ||
        f.name.toLowerCase().includes(q) || (f.description || "").toLowerCase().includes(q) ||
        f.id.toLowerCase().includes(q))
        && (q || showAll || !anyFeatured || f.featured || f.slug === activeSlug));
      if (!flows.length) continue;
      list.appendChild(el("p", { class: "kicker kicker--muted",
        style: { marginTop: "1.15rem", marginBottom: ".4rem" } }, g.name));
      for (const f of flows.sort((a, b) => a.name.localeCompare(b.name)))
        list.appendChild(el("a", {
          href: `#/d/${f.slug}`,
          style: { display: "block", fontSize: ".8125rem", lineHeight: "1.35",
            padding: ".3rem .55rem", marginLeft: "-.55rem", borderRadius: "3px",
            textDecoration: "none", color: f.slug === activeSlug ? "var(--ink)" : "var(--ink-2)",
            background: f.slug === activeSlug ? "var(--accent-soft)" : "transparent",
            fontWeight: f.slug === activeSlug ? "600" : "400",
            borderLeft: f.slug === activeSlug ? "2px solid var(--accent)" : "2px solid transparent" },
        }, textOf(`/d/${f.slug}`, "title", f.name)));
    }
    if (!list.childNodes.length)
      list.appendChild(el("p", { class: "figure__sub" }, "No datasets match that search."));

    if (!q && CAT.flows.some(f => !f.featured)) {
      const hidden = CAT.flows.filter(f => !f.featured).length;
      list.appendChild(el("button", { class: "railmore", "aria-pressed": String(showAll),
        onclick: () => { showAll = !showAll; paint(); } },
        showAll ? "Show fewer topics" : `Additional topics (${hidden})`));
    }
  };
  search.addEventListener("input", debounce(paint, 120));
  r.appendChild(search); r.appendChild(list); paint();
}

// ---------- pages ----------
function pageHome() {
  const m = main(); clear(m);
  const nObs = CAT.flows.reduce((a, f) => a + (f.n_obs || 0), 0);

  const H1 = "Numbers on the things that matter";
  const KICK = "An independent data publication";
  const hKick = el("p", { class: "kicker" }, textOf("/", "kicker", KICK));
  const hTitle = el("h1", {}, textOf("/", "title", H1));
  const STAND = "Visualizations of data on wages, unions, social spending, " +
    "inequalities, migration and taxation";
  const hStand = el("p", { class: "standfirst" }, textOf("/", "standfirst", STAND));
  editable(hKick, "/", "kicker", KICK);
  editable(hTitle, "/", "title", H1);
  editable(hStand, "/", "standfirst", STAND);
  m.appendChild(el("header", { style: { padding: "1.5rem 0 2.25rem", maxWidth: "44rem" } },
    hKick, hTitle,
    hStand,
    el("p", { class: "figure__sub", style: { marginTop: "1.1rem" } },
      `${CAT.flows.length} datasets · ${nObs ? nObs.toLocaleString("en-GB") + " observations · " : ""}` +
      `sourced live from OECD SDMX`)));

  const feat = el("section", {});
  m.appendChild(feat);
  renderFeatured(feat, CAT);

  m.appendChild(el("h2", { style: { marginBottom: "1.2rem" } }, "Every dataset"));

  for (const g of topTopics()) {
    const sec = el("section", { style: { marginBottom: "2.5rem" } });
    sec.appendChild(el("h2", { style: { marginBottom: ".2rem" } }, g.name));
    sec.appendChild(el("p", { class: "figure__sub", style: { marginBottom: ".9rem" } },
      `${g.flows.length} dataset${g.flows.length === 1 ? "" : "s"}`));
    const grid = el("div", { class: "cardgrid" });
    for (const f of g.flows.sort((a, b) => a.name.localeCompare(b.name)))
      grid.appendChild(el("a", { class: "cardgrid__i", href: `#/d/${f.slug}` },
        el("div", { class: "cardgrid__t" }, textOf(`/d/${f.slug}`, "title", f.name)),
        el("div", { class: "figure__sub" },
          topicLabel(CAT, f.topic).split(" › ").slice(1).join(" › ") || "—"),
        el("div", { class: "cardgrid__m" },
          `${(f.n_obs || 0).toLocaleString("en-GB")} observations` +
          (f.periods ? ` · ${f.periods[0]}–${f.periods[1]}` : ""))));
    sec.appendChild(grid);
    m.appendChild(sec);
  }
  m.appendChild(el("footer", { class: "figure__foot", style: { marginTop: "3rem" } },
    el("span", {}, "Data: OECD, via the SDMX public API. Rebuilt, not re-stated."),
    el("span", {}, `Built ${CAT.generated?.slice(0, 10) || ""}`)));
}

async function pageDataset(slug) {
  const f = CAT.flows.find(x => x.slug === slug);
  const m = main();
  m.dispatchEvent(new Event("explorer:teardown"));
  if (!f) { clear(m); m.appendChild(el("div", { class: "center-note" }, "Unknown dataset.")); return; }
  document.title = `${f.name} · Forest and the Trees`;
  await renderExplorer(m, slug, CAT);
}

// ---------- router ----------
let lastPath = null;
async function route(force = false) {
  const raw = location.hash.replace(/^#/, "") || "/";
  const h = raw.split("?")[0] || "/";
  if (h === lastPath && force !== true) return;  // query-only change: the explorer wrote it
  lastPath = h;
  const parts = h.split("/").filter(Boolean);
  if (parts[0] === "d" && parts[1]) {
    buildRail(parts[1]);
    await pageDataset(decodeURIComponent(parts[1]));
  } else {
    document.title = "Forest and the Trees";
    buildRail(null);
    pageHome();
  }
  window.scrollTo({ top: 0 });
  $$(".navlink").forEach(a => a.removeAttribute("aria-current"));
  const cur = h.startsWith("/d/") ? null : $(".navlink[href='#/']");
  cur?.setAttribute("aria-current", "page");
}

function initEditing() {
  const btn = document.getElementById("editbtn");
  const bar = document.getElementById("editbar");
  const count = document.getElementById("editcount");
  const paintCount = () => {
    const n = editCount();
    count.textContent = n ? `${n} change${n === 1 ? "" : "s"} saved in this browser` : "No changes yet";
  };
  const set = (on) => {
    setEditing(on);
    btn.setAttribute("aria-pressed", String(on));
    bar.hidden = !on;
    paintCount();
  };
  btn.addEventListener("click", () => set(!isEditing()));
  document.getElementById("doneedits").addEventListener("click", () => set(false));
  document.getElementById("exportedits").addEventListener("click", exportEdits);
  document.getElementById("resetedits").addEventListener("click", () => {
    const scope = location.hash.replace(/^#/, "").split("?")[0];
    resetScope(scope || "/");
    paintCount();
    route(true);
  });
  window.addEventListener("dv:edits", paintCount);
  paintCount();
}

async function boot() {
  initTheme();
  initEditing();
  await loadBaked(new URL("../data/overrides.json", import.meta.url).href);
  try { CAT = await getCatalog(); }
  catch (e) {
    main().innerHTML =
      `<div class="center-note">Could not load the catalog.<br><code>${e.message}</code></div>`;
    return;
  }
  window.addEventListener("hashchange", route);
  await route();
}
boot();
