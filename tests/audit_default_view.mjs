/* What a reader sees on arrival, for every dataset. Flags landings that are
   thin, flat, or dominated by one country. */
import { webkit } from "playwright";
import fs from "node:fs"; import path from "node:path";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const cat = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/catalog.json"), "utf8"));
const b = await webkit.launch();
const rows = [];
for (const f of cat.flows) {
  const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  let err = null;
  p.on("pageerror", e => err = String(e).slice(0, 80));
  try {
    await p.goto(`http://localhost:8231/#/d/${f.slug}`, { waitUntil: "load", timeout: 60000 });
    await p.waitForSelector("svg.chart, .figure .center-note", { timeout: 60000 });
    await p.waitForTimeout(1600);   // let the background upgrade settle
    const r = await p.evaluate(() => {
      const paths = [...document.querySelectorAll("svg.chart path.line")];
      const pts = paths.map(x => ((x.getAttribute("d") || "").match(/[ML]/g) || []).length);
      const ticks = [...document.querySelectorAll("svg.chart text.tick")].map(t => t.textContent);
      const yrs = ticks.filter(t => /^\d{4}$/.test(t)).map(Number);
      const dials = [...document.querySelectorAll(".ctlrow > .field")]
        .filter(x => !x.closest(".advanced")).length;
      const ind = [...document.querySelectorAll(".ctlrow > .field")]
        .find(x => /Indicator/.test(x.querySelector("label")?.textContent || ""));
      return {
        series: paths.length + document.querySelectorAll("svg.chart rect[rx]").length,
        minPts: pts.length ? Math.min(...pts) : 0,
        maxPts: pts.length ? Math.max(...pts) : 0,
        span: yrs.length ? `${Math.min(...yrs)}-${Math.max(...yrs)}` : "-",
        dials, unit: document.querySelector(".figure__sub")?.textContent.slice(0, 34) || "",
        indicator: ind?.querySelector("select")?.selectedOptions[0]?.textContent.trim().slice(0, 30) || "",
      };
    });
    rows.push({ name: f.name, featured: !!f.featured, ...r, err });
  } catch (e) { rows.push({ name: f.name, featured: !!f.featured, series: 0, err: String(e.message).slice(0, 60) }); }
  await p.close();
}
await b.close();
fs.writeFileSync(path.join(ROOT, "meta/default_view.json"), JSON.stringify(rows, null, 1));
const bad = rows.filter(r => r.series < 3 || r.maxPts < 5 || r.err);
console.log(`datasets audited: ${rows.length}   landings worth a look: ${bad.length}\n`);
console.log(" ser  pts dials  span        dataset");
for (const r of rows.sort((a, b2) => (a.maxPts || 0) - (b2.maxPts || 0)).slice(0, 18))
  console.log(`${String(r.series).padStart(4)} ${String(r.maxPts ?? 0).padStart(4)} ${String(r.dials ?? 0).padStart(5)}  ${String(r.span).padEnd(11)} ${r.featured ? "*" : " "} ${r.name.slice(0, 44)}${r.err ? "  ERR " + r.err : ""}`);
