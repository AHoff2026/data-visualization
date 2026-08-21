import { webkit } from "playwright";
const b = await webkit.launch();
const p = await b.newPage({ viewport:{width:1400,height:900} });
p.on("console", m=>{ if(m.type()==="error") console.log("CONSOLE:", m.text().slice(0,200)); });
p.on("pageerror", e=>console.log("PAGEERR:", String(e).slice(0,300)));
p.on("requestfailed", r=>console.log("REQFAIL:", r.url().slice(-60), r.failure()?.errorText));
let n=0, bytes=0;
p.on("response", r=>{ if(r.url().includes("/parts/")){ n++; } });
const t0=Date.now();
await p.goto("https://ahoff2026.github.io/data-visualization/#/d/OECD.SDD.TPS__DF_PDB", {waitUntil:"load"});
try {
  await p.waitForSelector("svg.chart", { timeout: 120000 });
  console.log(`chart rendered after ${((Date.now()-t0)/1000).toFixed(1)}s, ${n} part requests`);
} catch(e) {
  console.log(`TIMEOUT after ${((Date.now()-t0)/1000).toFixed(1)}s, ${n} part requests`);
  console.log("page state:", await p.evaluate(()=>document.querySelector("#main")?.textContent.slice(0,200)));
}
await b.close();
