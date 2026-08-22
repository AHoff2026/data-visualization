/* How many controls does each dataset actually present? */
import { webkit } from "playwright";
import fs from "node:fs"; import path from "node:path";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const cat = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/catalog.json"), "utf8"));
const b = await webkit.launch();
const rows = [];
for (const f of cat.flows) {
  const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  try {
    await p.goto(`http://localhost:8231/#/d/${f.slug}`, { waitUntil: "load", timeout: 60000 });
    await p.waitForSelector("svg.chart, .figure .center-note", { timeout: 60000 });
    await p.waitForTimeout(1600);
    const r = await p.evaluate(() => {
      const main = [...document.querySelectorAll(".ctlrow > .field")].filter(x => !x.closest(".advanced"));
      const adv = [...document.querySelectorAll(".advanced .field")];
      const inert = (document.body.textContent.match(/have a single value here|has a single value here/) || []).length;
      return { main: main.length, adv: adv.length, inert,
               labels: main.map(x => x.querySelector("label")?.textContent.trim()).join(", ") };
    });
    rows.push({ name: f.name, raw: 0, ...r });
  } catch { rows.push({ name: f.name, main: -1, adv: 0, labels: "error" }); }
  await p.close();
}
await b.close();
// how many dimensions does each dataset actually have?
for (const r of rows) {
  const f = cat.flows.find(x => x.name === r.name);
  const m = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/flows", f.slug, "meta.json"), "utf8"));
  r.raw = m.dims.filter(d => d.ids.length > 1).length;
}
rows.sort((a, b2) => b2.main - a.main);
const tot = rows.reduce((a, r) => a + r.main, 0), rawTot = rows.reduce((a, r) => a + r.raw, 0);
console.log(`dimensions in the data: ${rawTot}   dials actually shown: ${tot}   under Advanced: ${rows.reduce((a,r)=>a+r.adv,0)}\n`);
console.log("shown  dims  dataset");
for (const r of rows.slice(0, 14)) console.log(`${String(r.main).padStart(5)} ${String(r.raw).padStart(5)}  ${r.name.slice(0,34).padEnd(34)} ${r.labels.slice(0,62)}`);
