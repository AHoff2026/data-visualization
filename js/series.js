// ---------- pure series logic, shared by the explorer and the home page ----------
import { periodToNum } from "./util.js";
import { slotVar, SERIES_SLOTS } from "./chart.js";

export const TOTALISH = ["_T", "_Z", "TOT", "T"];

/** Codes OECD itself defaults to, else a "total" code, per dimension. */
export function desiredPicks(meta) {
  const od = meta.oecd_defaults || {};
  return meta.dims.map(d => {
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
  let best = null, bestScore = -1;
  for (const r of records) {
    let s = 0;
    for (let i = 0; i < D; i++) {
      if (i === breakdownIdx) continue;
      if (want[i] >= 0 && r.k[i] === want[i]) s++;
      else if (want[i] < 0) s += 0.01;
    }
    if (s > bestScore) { bestScore = s; best = r; if (s >= D - 1) break; }
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
    const f = r.m ? Math.pow(10, r.m) : 1;
    const points = r.t.map((ti, j) => ({
      x: periodToNum(meta.periods[ti]), y: r.v[j] * f, period: meta.periods[ti],
    })).filter(p => Number.isFinite(p.x) && Number.isFinite(p.y));
    if (!points.length) continue;
    const slot = slotOf ? slotOf(e) : out.length;
    const ctx = slot === undefined || slot < 0;
    out.push({ id: d.ids[e], label: d.names[e] || d.ids[e],
      color: ctx ? "var(--context)" : slotVar(slot), context: ctx, points });
  }
  return out;
}
