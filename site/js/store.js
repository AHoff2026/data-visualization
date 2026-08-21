// ---------- data access: catalog, flow meta, series (gzipped JSON) ----------
const BASE = new URL("../data/", import.meta.url).href;
const cache = new Map();
const inflight = new Map();

async function inflate(buf) {
  if (typeof DecompressionStream === "undefined")
    throw new Error("This browser cannot decompress the data files (needs DecompressionStream).");
  const s = new Blob([buf]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(s).text());
}

/** fetch with two retries — CDNs throttle when a page opens many files at once */
async function fetchRetry(url, tries = 3) {
  let last;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await fetch(url);
      if (r.ok) return r;
      last = new Error(`${r.status} ${r.statusText}`);
      if (r.status === 404) throw last;
    } catch (e) { last = e; }
    if (i < tries - 1) await new Promise(r => setTimeout(r, 400 * Math.pow(2, i)));
  }
  throw last;
}

async function getJSON(path, gz = false) {
  if (cache.has(path)) return cache.get(path);
  if (inflight.has(path)) return inflight.get(path);
  const p = (async () => {
    const r = await fetchRetry(BASE + path);
    const v = gz ? await inflate(await r.arrayBuffer()) : await r.json();
    cache.set(path, v);
    inflight.delete(path);
    return v;
  })().catch(e => { inflight.delete(path); throw e; });
  inflight.set(path, p);
  return p;
}

/** run tasks with bounded concurrency so we never open 50 sockets at once */
async function pool(items, limit, fn) {
  const out = new Array(items.length);
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (i < items.length) {
      const k = i++;
      out[k] = await fn(items[k], k);
    }
  }));
  return out;
}

export const getCatalog  = () => getJSON("catalog.json");
export const getFlowMeta = (slug) => getJSON(`flows/${slug}/meta.json`);

/**
 * Load series for a flow.
 *
 * Partitioned flows ship a small first-paint bundle holding just the opening
 * view, so a dataset draws in one request instead of a dozen. That bundle is
 * `partial`: it cannot answer "which other options have data", so the caller
 * should follow up with `{ allowBundle: false }` in the background.
 *
 * Returns { records, partial }.
 */
export async function getSeries(slug, areas = null, { allowBundle = true } = {}) {
  const meta = await getFlowMeta(slug);
  if (meta.layout === "single")
    return { records: await getJSON(`flows/${slug}/all.json.gz`, true), partial: false };

  const parts = meta.parts || {};
  const want = (areas && areas.length ? areas : Object.keys(parts)).filter(a => parts[a]);
  const bundle = meta.default_bundle;

  if (allowBundle && bundle && want.length && want.every(a => bundle.areas.includes(a))) {
    const all = await getJSON(`flows/${slug}/default.json.gz`, true);
    let records = all;
    if (want.length !== bundle.areas.length) {
      const ai = meta.dims.findIndex(d => d.id === meta.area_dim);
      if (ai >= 0) {
        const codes = meta.dims[ai].ids;
        const keep = new Set(want.map(a => codes.indexOf(a)));
        records = all.filter(r => keep.has(r.k[ai]));
      }
    }
    return { records, partial: !!bundle.partial };
  }

  const chunks = await pool(want, 6, a =>
    getJSON(`flows/${slug}/parts/${parts[a].file}`, true).catch(() => []));
  return { records: chunks.flat(), partial: false };
}

export const isCached = (slug) => cache.has(`flows/${slug}/meta.json`);
