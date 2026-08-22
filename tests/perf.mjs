/* How long does a reader wait, on the live site? */
import { webkit } from "playwright";
import fs from "node:fs"; import path from "node:path";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const cat = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/catalog.json"), "utf8"));
const B = process.env.BASE || "https://ahoff2026.github.io/data-visualization";
const pick = cat.flows.filter(f => f.featured).slice(0, 8);
const b = await webkit.launch();
const rows = [];
for (const f of pick) {
  const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  let bytes = 0;
  p.on("response", async r => { try { if (/\.(json|gz|css|js)/.test(r.url())) bytes += (await r.body()).length; } catch {} });
  const t0 = Date.now();
  await p.goto(`${B}/index.html?cb=${Date.now()}#/d/${f.slug}`, { waitUntil: "load", timeout: 90000 });
  await p.waitForSelector("svg.chart", { timeout: 90000 });
  const paint = Date.now() - t0;
  await p.waitForTimeout(2500);
  rows.push({ name: f.name, paint, kb: Math.round(bytes / 1024) });
  await p.close();
  await new Promise(r => setTimeout(r, 1200));
}
await b.close();
rows.sort((a, c) => c.paint - a.paint);
console.log("  paint      KB  dataset");
for (const r of rows) console.log(`${String(r.paint + "ms").padStart(7)} ${String(r.kb).padStart(7)}  ${r.name.slice(0, 42)}`);
const med = rows.map(r => r.paint).sort((a, c) => a - c)[Math.floor(rows.length / 2)];
console.log(`\nmedian time to first chart: ${med}ms`);
