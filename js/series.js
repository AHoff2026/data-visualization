// ---------- pure series logic, shared by the explorer and the home page ----------
import { periodToNum } from "./util.js?v=8dbbc407";
import { slotVar, SERIES_SLOTS } from "./chart.js?v=8dbbc407";

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
    // A total is the neutral place to start a cross-country comparison. OECD's
    // own DEFAULT annotation often points at a sub-category — employees rather
    // than all workers, 25-54 rather than every age — which quietly answers a
    // narrower question than the reader asked.
    for (const t of TOTALISH) { const j = d.ids.indexOf(t); if (j >= 0) return j; }
    // Not every total is coded "_T": "All educational institutions",
    // "All activities". Match on the label, preferring a plain total over one
    // that excludes a residual category.
    const byName = d.names
      .map((n, j) => [j, String(n || "")])
      .filter(([, n]) => /^(total|all\b)/i.test(n))
      .sort((a, b) => (/exclud/i.test(a[1]) - /exclud/i.test(b[1])) || a[1].length - b[1].length);
    if (byName.length) return byName[0][0];
    const code = od[d.id];
    if (code) {
      const j = d.ids.indexOf(String(code).split("+")[0]);
      if (j >= 0) return j;
    }
    return -1;
  });
}

/** Adopt the real record closest to the desired defaults, so picks are never empty. */
/**
 * @param constrain  dimension index -> code index that must hold. Technical
 *   dials are pinned before seeding; pinning them afterwards can invalidate the
 *   chosen unit, and the repair pass then gives up the unit rather than the
 *   transformation — which is exactly backwards.
 */
export function seedPicks(meta, records, breakdownIdx, constrain = null) {
  const want = desiredPicks(meta);
  const D = meta.dims.length;
  const weight = meta.dims.map(d =>
    d.id === "UNIT_MEASURE" ? 12 : d.id === "MEASURE" ? 4 : 1);

  // 1. Choose the unit first, ranking only units that actually carry records.
  //    A dataflow can declare a percentage it never publishes.
  const uIdx = meta.dims.findIndex(d => d.id === "UNIT_MEASURE");
  let pool = records;
  if (uIdx >= 0 && uIdx !== breakdownIdx) {
    const present = new Map();          // unit -> how many records carry it
    for (const r of records) present.set(r.k[uIdx], (present.get(r.k[uIdx]) || 0) + 1);
    const dim = meta.dims[uIdx];
    let bestU = -1, bestR = -1, bestN = -1;
    for (const [j, n] of present) {
      const rank = unitRank(dim.names[j]);
      // Rank first, then coverage: several units can tie at "a percentage", and
      // the best-covered one is the headline series rather than a niche cut.
      if (rank > bestR || (rank === bestR && n > bestN)) { bestR = rank; bestN = n; bestU = j; }
    }
    if (bestU >= 0) {
      want[uIdx] = bestU;
      const withUnit = records.filter(r => r.k[uIdx] === bestU);
      if (withUnit.length) pool = withUnit;
    }
  }

  // 2. Apply the technical pins inside that unit, but drop any pin that would
  //    empty it. OECD mislabels some level series as "Growth rate, period on
  //    period"; honouring that pin would bury every rate the dataset publishes.
  if (constrain) {
    for (const [i, j] of Object.entries(constrain)) {
      if (+i === breakdownIdx || +i === uIdx) continue;
      const sub = pool.filter(r => r.k[+i] === j);
      if (sub.length) { pool = sub; want[+i] = j; }
    }
  }

  let best = null, bestScore = -1;
  for (const r of pool) {
    let s = 0;
    for (let i = 0; i < D; i++) {
      if (i === breakdownIdx) continue;
      if (want[i] >= 0 && r.k[i] === want[i]) s += weight[i];
      else if (want[i] < 0) s += 0.01;
    }
    if (s > bestScore) { bestScore = s; best = r; }
  }
  if (!best) return new Array(D).fill(0);

  // Refine dimension by dimension: a record that matched on the unit may still
  // carry "Male" or "Growth rate" on the dimensions it did not match. Move each
  // one to its preferred value wherever data survives, so the opening view is
  // the plain, total, untransformed series.
  const picks = [...best.k];
  const order = meta.dims
    .map((d, i) => i)
    .filter(i => i !== breakdownIdx && want[i] >= 0)
    .sort((a, b) => weight[b] - weight[a]);
  for (let pass = 0; pass < 3; pass++) {
    let moved = false;
    for (const i of order) {
      if (picks[i] === want[i]) continue;
      const trial = [...picks]; trial[i] = want[i];
      const ok = records.some(r => {
        for (let j = 0; j < D; j++) {
          if (j === breakdownIdx) continue;
          if (r.k[j] !== trial[j]) return false;
        }
        return true;
      });
      if (ok) { picks[i] = want[i]; moved = true; }
    }
    if (!moved) break;
  }

  // A single-dial move can be blocked when two dials must move together —
  // "all workers" may only exist alongside "all ages". Take the record inside
  // the chosen unit that sits at the most preferred values at once, then let
  // the greedy pass finish the job.
  {
    const score = (k) => {
      let n = 0;
      for (const i of order) if (k[i] === want[i]) n++;
      return n;
    };
    let bestK = picks, bestN = score(picks);
    for (const r of pool) {
      const n = score(r.k);
      if (n > bestN) { bestN = n; bestK = r.k; }
    }
    if (bestK !== picks) {
      const next = [...bestK];
      for (const i of order) {
        if (next[i] === want[i]) continue;
        const trial = [...next]; trial[i] = want[i];
        const ok = records.some(r => {
          for (let j = 0; j < D; j++) {
            if (j === breakdownIdx) continue;
            if (r.k[j] !== trial[j]) return false;
          }
          return true;
        });
        if (ok) next[i] = want[i];
      }
      return next;
    }
  }
  return picks;
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
      // A series that is zero at every observation is the source's way of saying
      // "not reported": hours worked cannot be zero, nor a wage gap for 50 years.
      // Charting it draws a flat line on the axis floor and crushes the scale for
      // every country that did report.
    if (points.every(pt => pt.y === 0)) continue;
    const slot = slotOf ? slotOf(e) : out.length;
    const ctx = slot === undefined || slot < 0;
    out.push({ id: d.ids[e], label: d.names[e] || d.ids[e],
      color: ctx ? "var(--context)" : slotVar(slot), context: ctx, points });
  }
  return out;
}
