import { webkit } from "playwright";
import fs from "node:fs"; import path from "node:path";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const OUT = path.join(ROOT, "tests/shots"); fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE || "http://localhost:8231";
const targets = process.argv.slice(2);
const b = await webkit.launch();
for (const t of targets) {
  const [route, name, theme, w] = t.split("|");
  const page = await b.newPage({ viewport: { width: +(w||1400), height: 1000 } });
  await page.goto(BASE + route, { waitUntil: "load" });
  if (theme === "dark") { await page.evaluate(()=>document.documentElement.dataset.theme="dark"); }
  await page.waitForSelector("svg.chart, .sm-grid, h1", { timeout: 90000 });
  await page.evaluate(()=>window.dispatchEvent(new Event("resize")));
  await page.waitForTimeout(900);
  await page.screenshot({ path: path.join(OUT, name + ".png"), fullPage: true });
  console.log("shot:", name);
  await page.close();
}
await b.close();
