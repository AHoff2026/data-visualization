// ---------- pure series logic, shared by the explorer and the home page ----------
import { periodToNum } from "./util.js?v=2ff14d1d";
import { slotVar, SERIES_SLOTS } from "./chart.js?v=2ff14d1d";

export const TOTALISH = ["_T", "_Z", "TOT", "T"];

/**
 * How comparable a unit is across countries. Absolute counts tell you which
 * country is bigger, which is rarely the question; a share or a per-capita
 * figure tells you how countries differ. Higher scores are preferred.
 */
export function unitRank(name) {
  const n = String(name || "").toLowerCase();
  if (/percent|per cent|^%|share of/.test(n)) return 6;
  if (/per capita|per person|per head|per employee|per worker|per hour/.test(n)) return 5;
  if (/\brate\b|ratio|per 1 ?000|per thousand|per 100/.test(n)) return 4;
  if (/index/.test(n)) return 3;
  if (/dollar|euro|currency|ppp/.test(n)) return 2;
  if (/^(persons?|number|thousands?|millions?|units?|households?|head)/.test(n)) return 0;
  return 1;
}

/**
 * Codes to open on: a comparable unit first, then OECD's own DEFAULT
 * annotation, then a "total" code.
 */
export function desiredPicks(meta) {
  const od = meta.oecd_defaults || {};
  return meta.dims.map(d => {
    // Prefer a rate or share over a raw count, for units and for measures alike
    if (d.id === "UNIT_MEASURE" || d.id === "MEASURE") {
      let best = -1, bestScore = -1;
      d.names.forEach((n, j) => {
        let sc = d.id === "UNIT_MEASURE" ? unitRank(n)
               : (/\brate\b|percent|share|ratio|per capita/i.test(n) ? 5 : 1);
        if (od[d.id] && d.ids[j] === String(od[d.id]).split("+")[0]) sc += 0.5;
        if (sc > bestScore) { bestScore = sc; best = j; }
      });
      if (best >= 0 && bestScore >= (d.id === "UNIT_MEASURE" ? 3 : 5)) return best;
    }
    const code = od[d.id];
    if (code) {
      const j = d.ids.indexOf(String(code).split("+")[0]);
      if (j >= 0) return j;
    }
    for (const t of TOTALISH) { const j = d.ids.indexOf(t); if (j >= 0) return j; }
    return -1;
  });
}

/** Adopt the real record closest to the desired defaults, so picks are never empty. */
export function seedPicks(meta, records, breakdownIdx) {
  const want = desiredPicks(meta);
  const D = meta.dims.length;
  // The unit decides whether the chart is comparable at all, so it outweighs
  // the other dimensions; otherwise a record matching six incidental defaults
  // beats one that is actually expressed as a percentage.
  const weight = meta.dims.map(d =>
    d.id === "UNIT_MEASURE" ? 12 : d.id === "MEASURE" ? 4 : 1);
  let best = null, bestScore = -1;
  for (const r of records) {
    let s = 0;
    for (let i = 0; i < D; i++) {
      if (i === breakdownIdx) continue;
      if (want[i] >= 0 && r.k[i] === want[i]) s += weight[i];
      else if (want[i] < 0) s += 0.01;
    }
    if (s > bestScore) { bestScore = s; best = r; }
  }
  return best ? [...best.k] : new Array(D).fill(0);
}

/** One pass: records matching every fixed dim, plus per-dim conditional availability. */
export function scanRecords(meta, records, breakdownIdx, picks) {
  const D = meta.dims.length;
  const avail = meta.dims.map(() => new Set());
  const live = [];
  for (const r of records) {
    let miss = 0, missAt = -1;
    for (let i = 0; i < D; i++) {
      if (i === breakdownIdx) continue;
      if (r.k[i] !== picks[i]) { miss++; missAt = i; if (miss > 1) break; }
    }
    if (miss === 0) {
      live.push(r);
      for (let i = 0; i < D; i++) avail[i].add(r.k[i]);
    } else if (miss === 1) avail[missAt].add(r.k[missAt]);
  }
  return { live, avail };
}

/** Turn matching records into chart-ready series, honouring stable colour slots. */
export function toSeries(meta, live, breakdownIdx, entities, slotOf) {
  const d = meta.dims[breakdownIdx];
  const byEnt = new Map();
  for (const r of live) {
    const e = r.k[breakdownIdx];
    if (!entities.includes(e)) continue;
    const prev = byEnt.get(e);
    if (!prev || r.t.length > prev.t.length) byEnt.set(e, r);
  }
  const out = [];
  for (const e of entities) {
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
    const slot = slotOf ? slotOf(e) : out.length;
    const ctx = slot === undefined || slot < 0;
    out.push({ id: d.ids[e], label: d.names[e] || d.ids[e],
      color: ctx ? "var(--context)" : slotVar(slot), context: ctx, points });
  }
  return out;
}
