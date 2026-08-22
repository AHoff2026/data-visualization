/* Accessibility checks that can be verified rather than asserted. */
import { webkit } from "playwright";
import fs from "node:fs"; import path from "node:path";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const cat = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/catalog.json"), "utf8"));
const sample = ["/#/", ...cat.flows.slice(0, 8).map(f => `/#/d/${f.slug}`)];
const b = await webkit.launch();
const fails = [];
for (const route of sample) {
  const p = await b.newPage({ viewport: { width: 1400, height: 1000 } });
  await p.goto("http://localhost:8231" + route, { waitUntil: "load", timeout: 90000 });
  await p.waitForSelector("svg.chart, .feat, h1", { timeout: 90000 });
  await p.waitForTimeout(1500);
  const r = await p.evaluate(() => {
    const out = [];
    // charts must be labelled for a screen reader
    for (const s of document.querySelectorAll("svg.chart")) {
      if (!s.getAttribute("aria-label") && !s.querySelector("title")) out.push("chart without aria-label");
    }
    // every control must have a name
    for (const el of document.querySelectorAll("select")) {
      const id = el.closest(".field")?.querySelector("label")?.textContent?.trim();
      if (!id && !el.getAttribute("aria-label")) out.push("select without a label");
    }
    for (const el of document.querySelectorAll("button")) {
      const t = (el.textContent || "").trim();
      if (!t && !el.getAttribute("aria-label")) out.push("button without a name");
    }
    // one h1, and headings that do not skip levels
    const h = [...document.querySelectorAll("h1,h2,h3")].map(x => +x.tagName[1]);
    if (h.filter(x => x === 1).length !== 1) out.push(`${h.filter(x=>x===1).length} h1 elements`);
    for (let i = 1; i < h.length; i++) if (h[i] - h[i-1] > 1) out.push("heading level skipped");
    // images and links
    for (const a of document.querySelectorAll("a")) {
      if (!(a.textContent || "").trim() && !a.getAttribute("aria-label")) out.push("link without text");
    }
    return [...new Set(out)];
  });
  // keyboard: can we reach the first control by tabbing?
  await p.keyboard.press("Tab"); await p.keyboard.press("Tab");
  const focused = await p.evaluate(() => document.activeElement?.tagName + "." +
    (document.activeElement?.className || "").toString().slice(0, 20));
  if (r.length) fails.push({ route, issues: r });
  console.log(`${route.padEnd(42)} issues=${r.length}  focusAfterTab=${focused}`);
  await p.close();
}
await b.close();
console.log(`\npages checked: ${sample.length}   with issues: ${fails.length}`);
for (const f of fails) console.log(`  ${f.route}: ${f.issues.join("; ")}`);
