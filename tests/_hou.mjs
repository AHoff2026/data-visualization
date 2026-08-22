import { webkit } from "playwright";
const b=await webkit.launch(); const p=await b.newPage({viewport:{width:1400,height:1000}});
await p.goto("http://localhost:8231/#/d/OECD.SDD.TPS__DF_HOU_EAR",{waitUntil:"load"});
await p.waitForSelector("svg.chart",{timeout:90000}); await p.waitForTimeout(2000);
console.log(await p.evaluate(()=>{
  const ticks=[...document.querySelectorAll("svg.chart text.tick")].map(t=>t.textContent);
  const yrs=ticks.filter(t=>/^\d{4}$/.test(t));
  const pts=[...document.querySelectorAll("svg.chart path.line")].map(x=>((x.getAttribute("d")||"").match(/[ML]/g)||[]).length);
  const dials=[...document.querySelectorAll(".ctlrow > .field")].filter(f=>!f.closest(".advanced"))
    .map(f=>`${f.querySelector("label")?.textContent.trim()}=${f.querySelector("select")?.selectedOptions[0]?.textContent.trim()}`);
  const adv=[...document.querySelectorAll(".advanced .field")]
    .map(f=>`${f.querySelector("label")?.textContent.trim()}=${f.querySelector("select")?.selectedOptions[0]?.textContent.trim()}`);
  return JSON.stringify({xAxis:[yrs[0],yrs[yrs.length-1]], pointsPerLine:pts, dials, adv},null,1);
}));
await b.close();
