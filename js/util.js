// ---------- tiny DOM + formatting helpers ----------
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function el(tag, attrs = {}, ...kids) {
  const ns = /^(svg|g|path|line|rect|circle|text|tspan|polyline|clipPath|defs|use)$/.test(tag);
  const n = ns ? document.createElementNS("http://www.w3.org/2000/svg", tag)
               : document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.setAttribute("class", v);
    else if (k === "html") n.innerHTML = v;
    else if (k === "text") n.textContent = v;
    else if (k === "style" && typeof v === "object") Object.assign(n.style, v);
    else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
    else if (k === "dataset") for (const [dk, dv] of Object.entries(v)) n.dataset[dk] = dv;
    else n.setAttribute(k, v);
  }
  for (const k of kids.flat()) {
    if (k === null || k === undefined || k === false) continue;
    n.appendChild(typeof k === "object" ? k : document.createTextNode(String(k)));
  }
  return n;
}
export const clear = (n) => { while (n.firstChild) n.removeChild(n.firstChild); return n; };
export const frag = (...k) => { const f = document.createDocumentFragment();
  k.flat().forEach(x => x && f.appendChild(x)); return f; };

// ---------- numbers ----------
export function fmtNum(v, decimals) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  let d = decimals;
  if (d === undefined) d = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 1 ? 2 : a >= 0.01 ? 3 : 4;
  return v.toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });
}
export function fmtCompact(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e12) return (v / 1e12).toFixed(a >= 1e13 ? 0 : 1) + "tn";
  if (a >= 1e9)  return (v / 1e9 ).toFixed(a >= 1e10 ? 0 : 1) + "bn";
  if (a >= 1e6)  return (v / 1e6 ).toFixed(a >= 1e7  ? 0 : 1) + "m";
  if (a >= 1e4)  return (v / 1e3 ).toFixed(0) + "k";
  if (a >= 1000) return v.toLocaleString("en-GB", { maximumFractionDigits: 0 });
  if (a >= 1) return v.toFixed(a >= 100 ? 1 : 2).replace(/\.?0+$/, "");
  return v.toPrecision(2).replace(/0+$/, "").replace(/\.$/, "");
}
// nice axis ticks
export function niceTicks(min, max, count = 5) {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0, 1];
  if (min === max) { const p = Math.abs(min) || 1; min -= p * .1; max += p * .1; }
  const span = max - min;
  const raw = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
  const lo = Math.floor(min / step) * step, hi = Math.ceil(max / step) * step;
  const out = [];
  for (let v = lo; v <= hi + step * 1e-9; v += step) out.push(Math.round(v / step) * step);
  return out;
}
/** One formatter for an entire tick set — mixed units on one axis read as sloppy. */
export function axisFormatter(ticks) {
  const max = Math.max(...ticks.map(t => Math.abs(t)), 0);
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : max;
  let div = 1, suffix = "";
  if (max >= 1e12) { div = 1e12; suffix = "tn"; }
  else if (max >= 1e9) { div = 1e9; suffix = "bn"; }
  else if (max >= 1e6) { div = 1e6; suffix = "m"; }
  else if (max >= 1e4) { div = 1e3; suffix = "k"; }
  const sd = step / div;
  const dp = sd >= 10 ? 0 : sd >= 1 ? 0 : sd >= 0.1 ? 1 : sd >= 0.01 ? 2 : 3;
  return (v) => {
    const n = v / div;
    const txt = n.toLocaleString("en-GB", { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return (v === 0 ? "0" : txt) + (v === 0 ? "" : suffix);
  };
}

// ---------- period handling (annual / quarterly / monthly) ----------
export function periodParts(p) {
  let m = /^(\d{4})-?(Q)(\d)$/i.exec(p);      if (m) return { y:+m[1], sub:+m[3], freq:"Q" };
  m = /^(\d{4})-?(S)(\d)$/i.exec(p);          if (m) return { y:+m[1], sub:+m[3], freq:"S" };
  m = /^(\d{4})-(\d{2})$/.exec(p);            if (m) return { y:+m[1], sub:+m[2], freq:"M" };
  m = /^(\d{4})$/.exec(p);                    if (m) return { y:+m[1], sub:0,     freq:"A" };
  return { y: NaN, sub: 0, freq: "?" };
}
export function periodToNum(p) {
  const { y, sub, freq } = periodParts(p);
  if (!Number.isFinite(y)) return NaN;
  if (freq === "Q") return y + (sub - .5) / 4;
  if (freq === "S") return y + (sub - .5) / 2;
  if (freq === "M") return y + (sub - .5) / 12;
  return y;
}
export const periodYear = (p) => periodParts(p).y;

// ---------- misc ----------
export const debounce = (fn, ms = 160) => { let t; return (...a) => {
  clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
export const slugify = (s) => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
export const uniq = (a) => [...new Set(a)];
export function titleCase(s) {
  return String(s).replace(/\w\S*/g, t => t[0].toUpperCase() + t.slice(1).toLowerCase());
}
