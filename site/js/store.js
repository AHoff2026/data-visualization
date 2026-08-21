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

async function getJSON(path, gz = false) {
  if (cache.has(path)) return cache.get(path);
  if (inflight.has(path)) return inflight.get(path);
  const p = (async () => {
    const r = await fetch(BASE + path);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${path}`);
    const v = gz ? await inflate(await r.arrayBuffer()) : await r.json();
    cache.set(path, v);
    inflight.delete(path);
    return v;
  })();
  inflight.set(path, p);
  return p;
}

export const getCatalog  = () => getJSON("catalog.json");
export const getFlowMeta = (slug) => getJSON(`flows/${slug}/meta.json`);

/** Load series for a flow. For partitioned flows pass areas (array of REF_AREA codes). */
export async function getSeries(slug, areas = null) {
  const meta = await getFlowMeta(slug);
  if (meta.layout === "single") return getJSON(`flows/${slug}/all.json.gz`, true);
  const want = (areas && areas.length ? areas : Object.keys(meta.parts))
    .filter(a => meta.parts[a]);
  const chunks = await Promise.all(
    want.map(a => getJSON(`flows/${slug}/parts/${meta.parts[a].file}`, true).catch(() => []))
  );
  return chunks.flat();
}

export function partitionedAreas(meta) {
  return meta.layout === "parts" ? Object.keys(meta.parts) : null;
}
export const isCached = (slug) => cache.has(`flows/${slug}/meta.json`);
