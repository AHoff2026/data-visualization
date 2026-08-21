/* UNIT TESTS — pure functions that the charts depend on. */
import { axisFormatter, niceTicks, periodToNum, fmtNum, fmtCompact } from "../site/js/util.js";

let pass = 0, fail = 0;
const eq = (name, got, want) => {
  const a = JSON.stringify(got), b = JSON.stringify(want);
  if (a === b) { pass++; }
  else { fail++; console.log(`FAIL ${name}\n     got  ${a}\n     want ${b}`); }
};
const ok = (name, cond, detail = "") => {
  if (cond) pass++; else { fail++; console.log(`FAIL ${name} ${detail}`); }
};

// ---- axis ticks use exactly one unit
for (const t of [[0,5000,10000,15000],[0,2e6,4e6],[0,1e9,2e9],[0,25,50,75,100],[-20,-10,0,10,20]]) {
  const out = t.map(axisFormatter(t));
  const suf = new Set(out.filter(s => s !== "0").map(s => s.replace(/[\d.,-]/g, "")));
  ok(`axis one unit ${t[t.length-1]}`, suf.size <= 1, JSON.stringify(out));
}
eq("axis thousands", [0,5000,10000,15000].map(axisFormatter([0,5000,10000,15000])), ["0","5k","10k","15k"]);
eq("axis plain",     [0,25,50].map(axisFormatter([0,25,50])), ["0","25","50"]);

// ---- nice ticks bracket the data and are evenly spaced
for (const [lo, hi] of [[0,100],[3.2,7.8],[-5,5],[0,1],[1000,1e6],[0.001,0.009]]) {
  const t = niceTicks(lo, hi, 5);
  ok(`ticks bracket [${lo},${hi}]`, t[0] <= lo + 1e-9 && t[t.length-1] >= hi - 1e-9, JSON.stringify(t));
  const d = t.map((v,i) => i ? +(v - t[i-1]).toPrecision(6) : null).slice(1);
  ok(`ticks even [${lo},${hi}]`, new Set(d).size === 1, JSON.stringify(d));
}
ok("ticks on a flat series", niceTicks(5, 5, 5).length >= 2);

// ---- periods: annual, quarterly, monthly all sort correctly
const periods = ["2020","1999","2020-Q1","2020-Q4","2019-12","2019-01"];
const nums = periods.map(periodToNum);
ok("all periods parse", nums.every(Number.isFinite), JSON.stringify(nums));
ok("annual order", periodToNum("1999") < periodToNum("2020"));
ok("quarter order", periodToNum("2020-Q1") < periodToNum("2020-Q4"));
ok("month order", periodToNum("2019-01") < periodToNum("2019-12"));
ok("quarters sit inside their year",
  periodToNum("2020-Q1") > 2019.99 && periodToNum("2020-Q4") < 2021);

// ---- number formatting never emits NaN or undefined
for (const v of [0, 1, -1, 0.004, 12345.678, 1e9, null, undefined, NaN]) {
  const a = fmtNum(v), b = fmtCompact(v);
  ok(`fmt safe ${String(v)}`, !/NaN|undefined/.test(a + b), `${a} / ${b}`);
}
eq("fmtCompact millions", fmtCompact(2_400_000), "2.4m");
eq("fmtNum missing", fmtNum(null), "—");

console.log(`\n${"=".repeat(60)}\nUNIT TESTS  pass: ${pass}  fail: ${fail}`);
if (fail) process.exit(1);
console.log("ALL UNIT TESTS PASS");
