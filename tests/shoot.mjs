import { webkit } from "playwright";
import fs from "node:fs"; import path from "node:path";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const OUT = path.join(ROOT, "tests/shots"); fs.mkdirSync(OUT, { recursive: true });
const BASE = process.env.BASE || "http://localhost:8231";
const b = await webkit.launch();
for (const t of process.argv.slice(2)) {
  // route | name | theme | width | click:Label | crop:x,y,w,h
  const parts = t.split("|");
  const [route, name] = parts;
  const opt = Object.fromEntries(parts.slice(2).map(s => {
    const i = s.indexOf(":"); return i < 0 ? [s, true] : [s.slice(0, i), s.slice(i + 1)];
  }));
  const page = await b.newPage({ viewport: { width: +(opt.w || 1400), height: 1000 } });
  await page.goto(BASE + route, { waitUntil: "load" });
  if (opt.theme === "dark") await page.evaluate(() => document.documentElement.dataset.theme = "dark");
  await page.waitForSelector("svg.chart, .sm-grid, h1", { timeout: 90000 });
  if (opt.click) {
    await page.getByRole("button", { name: opt.click, exact: true }).click();
    await page.waitForTimeout(900);
  }
  await page.evaluate(() => window.dispatchEvent(new Event("resize")));
  await page.waitForTimeout(900);
  const clip = opt.crop
    ? (([x, y, w, h]) => ({ x: +x, y: +y, width: +w, height: +h }))(opt.crop.split(","))
    : undefined;
  await page.screenshot({ path: path.join(OUT, name + ".png"), fullPage: !clip, clip });
  console.log("shot:", name);
  await page.close();
}
await b.close();
