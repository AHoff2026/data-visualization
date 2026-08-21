/* Does any dataset open on a sub-category when a total exists? */
import { webkit } from "playwright";
import fs from "node:fs"; import path from "node:path";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const cat = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/catalog.json"), "utf8"));
const b = await webkit.launch();
const bad = [];
for (const f of cat.flows) {
  const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  try {
    await p.goto(`http://localhost:8231/#/d/${f.slug}`, { waitUntil: "load", timeout: 60000 });
    await p.waitForSelector("svg.chart, .figure .center-note", { timeout: 60000 });
    await p.waitForTimeout(1500);
    const r = await p.evaluate(() => {
      const out = [];
      for (const fld of document.querySelectorAll(".ctlrow > .field")) {
        if (fld.closest(".advanced")) continue;
        const lab = (fld.querySelector("label")?.textContent || "").trim();
        const sel = fld.querySelector("select"); if (!sel) continue;
        const cur = sel.selectedOptions[0]?.textContent.trim() || "";
        const opts = [...sel.options].map(o => o.textContent.trim());
        const total = opts.find(o => /^(total|all\b|both sexes)/i.test(o));
        if (total && cur !== total && !/not broken down/i.test(cur)) out.push({ lab, cur, total });
      }
      return out;
    });
    for (const x of r) bad.push({ flow: f.name, ...x });
  } catch {}
  await p.close();
}
await b.close();
console.log(`dials opening on a sub-category despite a total: ${bad.length}\n`);
for (const x of bad.slice(0, 24))
  console.log(`  ${x.lab.padEnd(18)} opens "${x.cur.slice(0,30)}" but "${x.total.slice(0,22)}" exists  ${x.flow.slice(0,32)}`);
