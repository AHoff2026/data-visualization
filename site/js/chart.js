// ---------- hand-rolled editorial SVG charts ----------
import { el, clear, niceTicks, fmtCompact, fmtNum, periodToNum, axisFormatter } from "./util.js?v=82f6a282";

export const SERIES_SLOTS = 13;
export const slotVar = (i) => `var(--s${(i % SERIES_SLOTS) + 1})`;

const NS = "http://www.w3.org/2000/svg";
const svgEl = (t, a = {}) => { const n = document.createElementNS(NS, t);
  for (const [k, v] of Object.entries(a)) if (v !== null && v !== undefined) n.setAttribute(k, v);
  return n; };

/**
 * Line chart.
 * series: [{ id, label, color|null, points:[{x:Number,y:Number,period:String}], context:Bool }]
 * Entities beyond the 8 categorical slots arrive with context:true and render gray.
 */
export function lineChart(host, series, opts = {}) {
  const {
    height = 380, yLabel = "", unit = "", decimals,
    directLabels = true, showDots = null, yZero = false, onZoom = null,
  } = opts;

  clear(host);
  host.classList.add("chartbox");
  const W = Math.max(320, host.clientWidth || 720);
  const live = series.filter(s => s.points.length);
  if (!live.length) {
    host.appendChild(el("div", { class: "center-note" }, "No observations for this selection."));
    return;
  }

  // ---- scales
  let xs = [], ys = [];
  for (const s of live) for (const p of s.points) { xs.push(p.x); ys.push(p.y); }
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  if (yZero) y0 = Math.min(0, y0);
  const ticks = niceTicks(y0, y1, height < 200 ? 3 : 5);
  const ty0 = Math.min(ticks[0], y0), ty1 = Math.max(ticks[ticks.length - 1], y1);

  // enough gutter for a real country name ("United Kingdom") even on teaser charts
  const labelRoom = directLabels ? Math.min(160, Math.max(96, W * .2)) : 12;
  const m = { t: 12, r: labelRoom, b: 26, l: 46 };
  const iw = Math.max(40, W - m.l - m.r), ih = Math.max(60, height - m.t - m.b);
  const sx = v => m.l + (x1 === x0 ? iw / 2 : (v - x0) / (x1 - x0) * iw);
  const sy = v => m.t + (ty1 === ty0 ? ih / 2 : ih - (v - ty0) / (ty1 - ty0) * ih);

  const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${W} ${height}`,
    role: "img", "aria-label": opts.ariaLabel || yLabel || "Line chart" });

  // ---- gridlines + y ticks (recessive)
  const fmtTick = axisFormatter(ticks);
  const gGrid = svgEl("g");
  for (const t of ticks) {
    const y = sy(t);
    if (y < m.t - 1 || y > m.t + ih + 1) continue;
    gGrid.appendChild(svgEl("line", { class: "gridline", x1: m.l, x2: m.l + iw, y1: y, y2: y }));
    const tk = svgEl("text", { class: "tick", x: m.l - 7, y: y + 3.5, "text-anchor": "end" });
    tk.textContent = fmtTick(t);
    gGrid.appendChild(tk);
  }
  svg.appendChild(gGrid);

  // ---- x axis ticks
  const gx = svgEl("g");
  const span = x1 - x0;
  const xt = niceTicks(x0, x1, Math.max(2, Math.min(8, Math.floor(iw / 78))))
    .filter(v => v >= x0 - 1e-9 && v <= x1 + 1e-9);
  const xticks = xt.length >= 2 ? xt : [x0, x1];
  for (const v of xticks) {
    const t = svgEl("text", { class: "tick", x: sx(v), y: m.t + ih + 17, "text-anchor": "middle" });
    t.textContent = span < 3 ? v.toFixed(1).replace(/\.0$/, "") : String(Math.round(v));
    gx.appendChild(t);
  }
  gx.appendChild(svgEl("line", { class: "axisline", x1: m.l, x2: m.l + iw,
    y1: m.t + ih, y2: m.t + ih }));
  svg.appendChild(gx);

  const path = pts => pts.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(2)},${sy(p.y).toFixed(2)}`).join("");

  // ---- context lines first (behind), then highlighted
  const ctx = live.filter(s => s.context), hot = live.filter(s => !s.context);
  const gC = svgEl("g");
  for (const s of ctx) {
    const p = svgEl("path", { class: "line line--context", d: path(s.points) });
    p.dataset.sid = s.id;
    gC.appendChild(p);
  }
  svg.appendChild(gC);

  const gH = svgEl("g");
  const dotOn = showDots === null ? hot.some(s => s.points.length <= 30) : showDots;
  for (const s of hot) {
    gH.appendChild(svgEl("path", { class: "halo", d: path(s.points) }));
    const p = svgEl("path", { class: "line", d: path(s.points), stroke: s.color });
    p.dataset.sid = s.id;
    gH.appendChild(p);
    if (dotOn && s.points.length <= 40)
      for (const pt of s.points)
        gH.appendChild(svgEl("circle", { class: "dot", cx: sx(pt.x), cy: sy(pt.y), fill: s.color }));
  }
  svg.appendChild(gH);

  // ---- direct labels at line ends, de-collided.
  // Context lines are labelled too: with more series than palette slots,
  // identity must not rest on colour alone.
  if (directLabels && live.length) {
    const ends = live.map(s => {
      const last = s.points[s.points.length - 1];
      return { s, x: sx(last.x), y: sy(last.y), v: last.y };
    }).sort((a, b) => a.y - b.y);
    const MIN = 12.5;
    for (let i = 1; i < ends.length; i++)
      if (ends[i].y - ends[i - 1].y < MIN) ends[i].y = ends[i - 1].y + MIN;
    const over = ends.length ? ends[ends.length - 1].y - (m.t + ih) : 0;
    if (over > 0) for (const e of ends) e.y -= over;
    const gL = svgEl("g");
    for (const e of ends) {
      const short = truncate(e.s.label, Math.floor(labelRoom / 5.9));
      const t = svgEl("text", { class: "serieslabel", x: m.l + iw + 8,
        y: Math.max(m.t + 8, e.y) + 3.5,
        fill: e.s.context ? "var(--ink-muted)" : e.s.color });
      if (e.s.context) t.setAttribute("font-weight", "500");
      t.textContent = short;
      if (short !== e.s.label) {
        const ttl = svgEl("title"); ttl.textContent = e.s.label; t.appendChild(ttl);
      }
      gL.appendChild(t);
    }
    svg.appendChild(gL);
  }

  host.appendChild(svg);

  // ---- crosshair + tooltip
  const tip = el("div", { class: "tooltip" });
  host.appendChild(tip);
  const cross = svgEl("line", { class: "crosshair", y1: m.t, y2: m.t + ih, opacity: 0 });
  svg.appendChild(cross);
  const marks = svgEl("g"); svg.appendChild(marks);

  const allX = [...new Set(live.flatMap(s => s.points.map(p => p.x)))].sort((a, b) => a - b);
  const brush = svgEl("rect", { y: m.t, height: ih, fill: "var(--accent)",
    opacity: .12, x: 0, width: 0, "pointer-events": "none" });
  svg.appendChild(brush);
  const hit = svgEl("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent",
    style: "cursor:crosshair" });
  svg.appendChild(hit);

  const hide = () => { cross.setAttribute("opacity", 0); clear(marks); tip.dataset.show = "0"; };
  const move = (ev) => {
    const r = svg.getBoundingClientRect();
    const px = (ev.clientX - r.left) / r.width * W;
    const xv = x0 + (px - m.l) / iw * (x1 - x0);
    let best = allX[0], bd = Infinity;
    for (const v of allX) { const d = Math.abs(v - xv); if (d < bd) { bd = d; best = v; } }
    const cx = sx(best);
    cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("opacity", 1);
    clear(marks);
    const rows = [];
    for (const s of live) {
      const p = s.points.find(q => q.x === best);
      if (!p) continue;
      rows.push({ s, p });
      marks.appendChild(svgEl("circle", { cx, cy: sy(p.y), r: 4,
        fill: s.context ? "var(--context)" : s.color, stroke: "var(--paper)", "stroke-width": 2 }));
    }
    if (!rows.length) { tip.dataset.show = "0"; return; }

    // Minimalist read-out: the period, the series nearest the pointer, and one
    // line placing it among the rest. A twelve-row dump is unreadable.
    const ry = (ev.clientY - r.top) / r.height * height;
    let near = rows[0], nd = Infinity;
    for (const q of rows) {
      const d = Math.abs(sy(q.p.y) - ry);
      if (d < nd) { nd = d; near = q; }
    }
    const vals = rows.map(q => q.p.y).sort((a, b) => a - b);
    const rank = vals.length - vals.indexOf(near.p.y);

    clear(tip);
    tip.appendChild(el("div", { class: "tip__p" }, near.p.period));
    tip.appendChild(el("div", { class: "tip__s" },
      el("span", { class: "dotmark", style: { background: near.s.color } }),
      truncate(near.s.label, 26)));
    tip.appendChild(el("div", { class: "tip__v" },
      fmtNum(near.p.y, decimals) + shortUnit(unit)));

    // emphasise the nearest point
    clear(marks);
    for (const { s: ss, p } of rows)
      marks.appendChild(svgEl("circle", { cx, cy: sy(p.y),
        r: ss === near.s ? 5 : 3,
        fill: ss === near.s ? ss.color : "var(--paper)",
        stroke: ss === near.s ? "var(--paper)" : ss.color,
        "stroke-width": ss === near.s ? 2 : 1.5,
        opacity: ss === near.s ? 1 : .75 }));

    tip.dataset.show = "1";
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    const hx = cx / W * host.clientWidth;
    tip.style.left = Math.max(4, Math.min(host.clientWidth - tw - 4, hx + 14)) + "px";
    tip.style.top = Math.max(4, Math.min(height - th - 4,
      (ev.clientY - svg.getBoundingClientRect().top) - th - 12)) + "px";
  };
  // ---- drag across the plot to zoom the time axis
  let dragFrom = null;
  const xAt = (ev) => {
    const r = svg.getBoundingClientRect();
    const px = (ev.clientX - r.left) / r.width * W;
    return Math.min(m.l + iw, Math.max(m.l, px));
  };
  const clearBrush = () => { brush.setAttribute("width", 0); dragFrom = null; };

  hit.addEventListener("pointerdown", (ev) => {
    if (!onZoom) { move(ev); return; }
    dragFrom = xAt(ev);
    hide();
    hit.setPointerCapture?.(ev.pointerId);
  });
  hit.addEventListener("pointermove", (ev) => {
    if (dragFrom === null) { move(ev); return; }
    const x = xAt(ev);
    brush.setAttribute("x", Math.min(dragFrom, x));
    brush.setAttribute("width", Math.abs(x - dragFrom));
  });
  const finish = (ev) => {
    if (dragFrom === null) return;
    const x = xAt(ev);
    const px = Math.abs(x - dragFrom);
    const from = x0 + (Math.min(dragFrom, x) - m.l) / iw * (x1 - x0);
    const to   = x0 + (Math.max(dragFrom, x) - m.l) / iw * (x1 - x0);
    clearBrush();
    if (px > 6 && onZoom) onZoom(from, to);
  };
  hit.addEventListener("pointerup", finish);
  hit.addEventListener("pointercancel", clearBrush);
  hit.addEventListener("pointerleave", (ev) => { if (dragFrom === null) hide(); });
  return svg;
}

/** A unit as a symbol, not a sentence. Percentages get "%"; everything else
 *  shows the bare number — the unit is already named above the chart. */
export function shortUnit(name) {
  const n = String(name || "").toLowerCase();
  if (n.includes("percent") || n.startsWith("%")) return "%";
  if (n.includes("per thousand")) return "\u2030";
  return "";
}

function ord(n) {
  const t = n % 100;
  if (t >= 11 && t <= 13) return n + "th";
  return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
}

function truncate(s, n) {
  s = String(s);
  return s.length <= n ? s : s.slice(0, Math.max(3, n - 1)).trimEnd() + "…";
}

/**
 * Small multiples: one panel per entity, each against a grey backdrop of the others.
 * scale "shared" makes panels comparable; "own" lets each panel show its own shape.
 * "auto" picks: with a wide spread of magnitudes a shared scale flattens the small
 * panels into straight lines, which hides exactly what the reader came for.
 */
export function smallMultiples(host, series, opts = {}) {
  const { height = 84, unit = "", decimals, backdrop = true, scale = "auto" } = opts;
  clear(host);
  const live = series.filter(s => s.points.length);
  if (!live.length) {
    host.appendChild(el("div", { class: "center-note" }, "No observations for this selection."));
    return { scale: null };
  }

  const spans = live.map(s => {
    const ys = s.points.map(p => p.y);
    return { lo: Math.min(...ys), hi: Math.max(...ys) };
  });
  // Compare the largest panel with a low quantile rather than the median: it is
  // the smallest panels that a shared scale flattens into straight lines.
  const mags = spans.map(v => Math.max(Math.abs(v.hi), Math.abs(v.lo))).sort((a, b) => a - b);
  const low = mags[Math.floor(mags.length * 0.2)] || mags[0] || 1;
  const top = mags[mags.length - 1] || 1;
  const mode = scale === "auto" ? (top / Math.max(low, 1e-9) > 10 ? "own" : "shared") : scale;

  let xs = [];
  for (const s of live) for (const p of s.points) xs.push(p.x);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const gLo = Math.min(...spans.map(v => v.lo));
  const gHi = Math.max(...spans.map(v => v.hi));

  const grid = el("div", { class: "sm-grid" });
  live.forEach((s, idx) => {
    const W = 200, H = height, m = { t: 7, r: 7, b: 5, l: 7 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const lo = mode === "shared" ? gLo : spans[idx].lo;
    const hi = mode === "shared" ? gHi : spans[idx].hi;
    const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.08 || 1;
    const yl = lo - pad, yh = hi + pad;
    const sx = v => m.l + (x1 === x0 ? iw / 2 : (v - x0) / (x1 - x0) * iw);
    const sy = v => m.t + (yh === yl ? ih / 2 : ih - (v - yl) / (yh - yl) * ih);
    const path = pts => pts.map((p, i) =>
      `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.y).toFixed(1)}`).join("");

    const svg = svgEl("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`,
      preserveAspectRatio: "none", style: `height:${H}px` });
    if (backdrop && mode === "shared")
      for (const o of live) {
        if (o === s) continue;
        svg.appendChild(svgEl("path", { d: path(o.points), fill: "none",
          stroke: "var(--context)", "stroke-width": .75, opacity: .55 }));
      }
    svg.appendChild(svgEl("path", { d: path(s.points), fill: "none",
      stroke: s.color || "var(--accent)", "stroke-width": 1.75, "stroke-linejoin": "round" }));
    const last = s.points[s.points.length - 1];
    svg.appendChild(svgEl("circle", { cx: sx(last.x), cy: sy(last.y), r: 2.5,
      fill: s.color || "var(--accent)" }));

    grid.appendChild(el("div", { class: "sm-cell",
      title: `${s.label} · ${last.period}: ${fmtNum(last.y, decimals)}${unit ? " " + unit : ""}` },
      el("div", { class: "sm-cell__t" },
        el("span", {}, truncate(s.label, 18)),
        el("span", { class: "sm-cell__v" }, fmtCompact(last.y))),
      svg,
      mode === "own"
        ? el("div", { class: "sm-cell__r" }, `${fmtCompact(spans[idx].lo)}–${fmtCompact(spans[idx].hi)}`)
        : null));
  });
  host.appendChild(grid);
  return { scale: mode };
}

/**
 * Render a chart and keep it matched to its container.
 * Charts measure their host to build a viewBox; if the host is measured before
 * layout settles (grid/flex children, late fonts) the aspect ratio is wrong.
 * A ResizeObserver re-renders on any real width change and fixes that class of
 * bug permanently.
 */
export function autosize(host, render) {
  let last = 0, raf = 0;
  const run = () => {
    const w = host.clientWidth;
    if (!w || Math.abs(w - last) < 2) return;
    last = w;
    render(host, w);
  };
  render(host, host.clientWidth || 720);
  last = host.clientWidth;
  const ro = new ResizeObserver(() => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(run);
  });
  ro.observe(host);
  return () => { ro.disconnect(); cancelAnimationFrame(raf); };
}
