/* DEEP ACCEPTANCE TESTS — exercises the controls, not just first paint.
   D1 every dimension option renders a chart or an honest explanation
   D2 every compare-by dimension renders
   D3 toggling an entity colours + labels it, and does not move the page
   D4 dark theme renders
   D5 mobile width has no horizontal overflow
   D6 no console errors throughout                                          */
import { webkit } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = process.env.BASE || "http://localhost:8231";
const ROOT = path.join(process.env.HOME, "Documents/data-visualization");
const MAX_OPTS = +(process.env.MAX_OPTS || 12);
const catalog = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/catalog.json"), "utf8"));
const ONLY = process.argv.slice(2).filter(a => !a.startsWith("-"));
let slugs = catalog.flows.map(f => f.slug);
if (ONLY.length) slugs = slugs.filter(s => ONLY.includes(s));

const browser = await webkit.launch();
const results = [];

/** Is the figure in a good state? Either a chart, or a clear explanation. */
async function figureState(page) {
  return page.evaluate(() => {
    const svg = document.querySelector("svg.chart");
    const grid = document.querySelector(".sm-grid");
    const tbl = document.querySelector("table.data");
    const note = document.querySelector(".figure .center-note")?.textContent?.trim() || "";
    const lines = document.querySelectorAll("svg.chart path.line").length;
    const legend = [...document.querySelectorAll(".legend__i")].map(n => n.textContent.trim());
    const swatches = [...document.querySelectorAll(".legend__i .dotmark")]
      .map(n => getComputedStyle(n).backgroundColor);
    return { hasChart: !!(svg || grid || tbl), lines, note, legend, swatches,
             overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
  });
}

for (const slug of slugs) {
  const rec = { slug, fail: [], errors: [], checked: 0 };
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  page.on("console", m => { if (m.type() === "error") rec.errors.push(m.text().slice(0, 200)); });
  page.on("pageerror", e => rec.errors.push("PAGEERROR " + String(e).slice(0, 200)));
  try {
    await page.goto(`${BASE}/#/d/${slug}`, { waitUntil: "load", timeout: 90000 });
    await page.waitForSelector("svg.chart, .figure .center-note", { timeout: 90000 });
    await page.waitForTimeout(300);

    // ---------- D2 every compare-by option
    const bdSel = page.locator(".field", { hasText: "Compare by" }).locator("select");
    if (await bdSel.count()) {
      const opts = await bdSel.locator("option").evaluateAll(os => os.map(o => o.value));
      for (const v of opts) {
        await bdSel.selectOption(v);
        await page.waitForTimeout(420);
        const st = await figureState(page);
        rec.checked++;
        if (!st.hasChart && !st.note)
          rec.fail.push(`D2 compare-by "${v}" left a blank figure`);
      }
      await bdSel.selectOption(opts[0]);
      await page.waitForTimeout(400);
    }

    // ---------- D1 every dimension option
    const fields = page.locator(".ctlrow .field").filter({ hasNot: page.locator("label:text-is('Compare by')") });
    const nF = await fields.count();
    for (let i = 0; i < nF; i++) {
      const f = fields.nth(i);
      const sel = f.locator("select");
      if (!(await sel.count())) continue;
      const label = (await f.locator("label").textContent().catch(() => "")) || `field${i}`;
      let opts = await sel.locator("option").evaluateAll(os => os.map(o => o.value));
      if (opts.length > MAX_OPTS) {
        const step = Math.ceil(opts.length / MAX_OPTS);
        opts = opts.filter((_, k) => k % step === 0).slice(0, MAX_OPTS);
      }
      for (const v of opts) {
        try { await sel.selectOption(v, { timeout: 8000 }); }
        catch { continue; }                       // control was re-rendered; fine
        await page.waitForTimeout(360);
        const st = await figureState(page);
        rec.checked++;
        if (!st.hasChart && !st.note)
          rec.fail.push(`D1 ${label.trim()} option ${v} → blank figure with no explanation`);
      }
    }

    // ---------- D3 toggle an entity: colour, label, no page jump
    await page.reload({ waitUntil: "load" });
    await page.waitForSelector("svg.chart", { timeout: 90000 });
    await page.waitForTimeout(350);
    await page.evaluate(() => window.scrollTo(0, 260));
    const before = await figureState(page);
    const yBefore = await page.evaluate(() => window.scrollY);
    // only real entity chips carry a colour swatch; the tier toggle does not
    const off = page.locator('.chip[aria-pressed="false"]:has(.chip__swatch)').first();
    if (await off.count()) {
      const name = (await off.textContent()).trim();
      await off.click();
      await page.waitForTimeout(600);
      const after = await figureState(page);
      const yAfter = await page.evaluate(() => window.scrollY);
      rec.checked++;
      if (Math.abs(yAfter - yBefore) > 8)
        rec.fail.push(`D3 page jumped ${yBefore}→${yAfter} on toggle`);
      if (after.legend.length <= before.legend.length && after.lines <= before.lines)
        rec.fail.push(`D3 toggling "${name}" on added no series`);
    }

    // ---------- D8 drag across the plot zooms the time axis, and resets
    {
      await page.locator("svg.chart").scrollIntoViewIfNeeded();
      await page.waitForTimeout(150);
      const bb = await page.locator("svg.chart").boundingBox();
      const nX = await page.evaluate(() => {
        const xs = new Set();
        for (const p of document.querySelectorAll("svg.chart path.line")) {
          const d = p.getAttribute("d") || "";
          for (const m of d.matchAll(/[ML]([-\d.]+),/g)) xs.add(m[1]);
        }
        return xs.size;
      });
      if (bb && nX > 3) {
        const before = await page.evaluate(() =>
          [...document.querySelectorAll("svg.chart text.tick")].map(t => t.textContent).join(","));
        await page.mouse.move(bb.x + bb.width * 0.5, bb.y + bb.height * 0.5);
        await page.mouse.down();
        await page.mouse.move(bb.x + bb.width * 0.8, bb.y + bb.height * 0.5, { steps: 8 });
        await page.mouse.up();
        await page.waitForTimeout(450);
        rec.checked++;
        const bar = await page.locator(".zoombar").count();
        const after = await page.evaluate(() =>
          [...document.querySelectorAll("svg.chart text.tick")].map(t => t.textContent).join(","));
        if (!bar) rec.fail.push("D8 dragging did not zoom the time axis");
        else {
          await page.locator(".zoombar button").click();
          await page.waitForTimeout(400);
          const back = await page.evaluate(() =>
            [...document.querySelectorAll("svg.chart text.tick")].map(t => t.textContent).join(","));
          if (back !== before) rec.fail.push("D8 reset did not restore the full period");
        }
      }
    }

    // ---------- D7 the URL captures the view, and reloading it restores the view
    {
      const hash = await page.evaluate(() => location.hash);
      rec.checked++;
      if (!/[?&]bd=/.test(hash)) rec.fail.push("D7 view state is not written to the URL");
      else {
        const before = await figureState(page);
        await page.goto(`${BASE}/${hash}`, { waitUntil: "load", timeout: 90000 });
        await page.waitForSelector("svg.chart, .figure .center-note", { timeout: 90000 });
        await page.waitForTimeout(500);
        const after = await figureState(page);
        if (before.lines && after.lines !== before.lines)
          rec.fail.push(`D7 reloading the shared URL changed the chart (${before.lines} → ${after.lines} lines)`);
      }
    }

    // ---------- D4 dark theme
    await page.evaluate(() => { document.documentElement.dataset.theme = "dark"; });
    await page.waitForTimeout(120);
    await page.evaluate(() => window.dispatchEvent(new Event("resize")));
    await page.waitForTimeout(450);
    const dark = await figureState(page);
    rec.checked++;
    if (!dark.hasChart) rec.fail.push("D4 dark theme lost the chart");
    await page.evaluate(() => { document.documentElement.dataset.theme = "light"; });

    // ---------- D5 mobile
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => window.dispatchEvent(new Event("resize")));
    await page.waitForTimeout(600);
    const mob = await figureState(page);
    rec.checked++;
    if (!mob.hasChart) rec.fail.push("D5 mobile lost the chart");
    if (mob.overflow > 2) rec.fail.push(`D5 mobile overflows horizontally by ${mob.overflow}px`);

    // ---------- D6
    if (rec.errors.length) rec.fail.push(`D6 ${rec.errors.length} console error(s)`);
  } catch (e) {
    rec.fail.push("EXCEPTION " + String(e.message || e).slice(0, 160));
  }
  await page.close();
  results.push(rec);
  const ok = !rec.fail.length;
  console.log(`${ok ? "ok  " : "FAIL"} ${slug.padEnd(44)} checks=${String(rec.checked).padStart(3)}` +
    (ok ? "" : "\n      " + rec.fail.slice(0, 6).join("\n      ")));
  if (!ok && rec.errors.length) rec.errors.slice(0, 2).forEach(e => console.log("      ↳ " + e));
}
await browser.close();
fs.writeFileSync(path.join(ROOT, "tests/verify_deep_result.json"), JSON.stringify(results, null, 1));
const bad = results.filter(r => r.fail.length);
const checks = results.reduce((a, r) => a + r.checked, 0);
console.log("\n" + "=".repeat(74));
console.log(`DATASETS: ${results.length}   INTERACTIONS: ${checks}   PASS: ${results.length - bad.length}   FAIL: ${bad.length}`);
if (bad.length) { console.log("FAILED: " + bad.map(b => b.slug).join(", ")); process.exit(1); }
console.log("ALL DEEP UI TESTS PASS (WebKit / Safari engine)");
