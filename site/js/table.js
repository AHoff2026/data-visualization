// ---------- table view (also the accessibility relief for low-contrast marks) ----------
import { el, clear, fmtNum } from "./util.js?v=7c14341d";

export function dataTable(host, series, opts = {}) {
  const { unit = "", decimals } = opts;
  clear(host);
  if (!series.length) {
    host.appendChild(el("div", { class: "center-note" }, "No observations for this selection."));
    return;
  }
  const periods = [...new Set(series.flatMap(s => s.points.map(p => p.period)))]
    .sort((a, b) => {
      const na = series[0] ? 0 : 0;
      return cmpPeriod(a, b);
    });

  const thead = el("thead", {}, el("tr", {},
    el("th", { scope: "col" }, "Series"),
    ...periods.map(p => el("th", { scope: "col" }, p))));

  const tbody = el("tbody");
  for (const s of series) {
    const by = new Map(s.points.map(p => [p.period, p.y]));
    tbody.appendChild(el("tr", {},
      el("th", { scope: "row", style: { fontWeight: "600" } },
        el("span", { class: "dotmark", style: { background: s.color, display: "inline-block",
          marginRight: ".4rem", verticalAlign: "middle" } }),
        s.label),
      ...periods.map(p => el("td", {}, by.has(p) ? fmtNum(by.get(p), decimals) : "—"))));
  }

  const wrap = el("div", { class: "tablewrap", style: { maxHeight: "30rem" } },
    el("table", { class: "data" }, thead, tbody));
  host.appendChild(wrap);

  host.appendChild(el("div", { class: "figure__sub", style: { marginTop: ".5rem" } },
    `${series.length} series × ${periods.length} periods${unit ? " · " + unit : ""}`,
    " · ",
    el("button", { class: "chip", onclick: () => downloadCSV(series, periods, opts) }, "Download CSV")));
}

function cmpPeriod(a, b) {
  const pa = parse(a), pb = parse(b);
  return pa.y - pb.y || pa.s - pb.s || String(a).localeCompare(String(b));
}
function parse(p) {
  let m = /^(\d{4})-?[QSM]?(\d{1,2})?$/i.exec(p);
  if (m) return { y: +m[1], s: +(m[2] || 0) };
  return { y: 9999, s: 0 };
}

export function downloadCSV(series, periods, opts = {}) {
  const q = v => /[",\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
  const lines = [["Series", ...periods].map(q).join(",")];
  for (const s of series) {
    const by = new Map(s.points.map(p => [p.period, p.y]));
    lines.push([s.label, ...periods.map(p => by.has(p) ? by.get(p) : "")].map(q).join(","));
  }
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (opts.filename || "oecd-series") + ".csv";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
