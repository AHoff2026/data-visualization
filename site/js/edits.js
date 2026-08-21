// ---------- manual text overrides ----------
// Titles and descriptions can be edited in place. Overrides live in this
// browser's localStorage (the site is static, so there is no server to save
// to) and can be exported as JSON to be baked into the build permanently.
const KEY = "dv.edits.v1";
let store = load();
// Baked-in overrides shipped with the site. Local edits layer on top of these,
// so a change made in the browser still wins until it is exported and baked in.
let baked = {};
let editing = false;
const listeners = new Set();

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) || "{}"); }
  catch { return {}; }
}
function persist() {
  try { localStorage.setItem(KEY, JSON.stringify(store)); } catch {}
}

/** Load the shipped overrides. Called once at boot, before the first render. */
export async function loadBaked(url) {
  try {
    const r = await fetch(url);
    if (r.ok) baked = await r.json();
  } catch { /* the site works fine without them */ }
}

/** The text to show: a local edit, else a baked override, else the original. */
export function textOf(scope, field, original) {
  if (store[scope] && store[scope][field] !== undefined) return store[scope][field];
  if (baked[scope] && baked[scope][field] !== undefined) return baked[scope][field];
  return original;
}

/** What an unedited field reverts to — the baked text, not the OECD original. */
export const baseOf = (scope, field, original) =>
  (baked[scope] && baked[scope][field] !== undefined) ? baked[scope][field] : original;

export const isEdited = (scope, field) =>
  !!(store[scope] && store[scope][field] !== undefined);

export function setText(scope, field, value, original) {
  if (value === baseOf(scope, field, original)) {
    if (store[scope]) { delete store[scope][field];
      if (!Object.keys(store[scope]).length) delete store[scope]; }
  } else {
    store[scope] = store[scope] || {};
    store[scope][field] = value;
  }
  persist();
}

export function resetScope(scope) { delete store[scope]; persist(); }
export const allEdits = () => JSON.parse(JSON.stringify(store));
export const editCount = () =>
  Object.values(store).reduce((a, o) => a + Object.keys(o).length, 0);

export const isEditing = () => editing;
export function onEditModeChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export function setEditing(on) {
  editing = !!on;
  document.documentElement.dataset.editing = editing ? "1" : "";
  listeners.forEach(fn => fn(editing));
}

/**
 * Make one element editable when edit mode is on.
 * `plain` keeps the value as text (titles); otherwise innerHTML is kept so a
 * description's links and paragraphs survive.
 */
export function editable(node, scope, field, original, { plain = true } = {}) {
  node.dataset.editField = field;
  node.dataset.editScope = scope;
  node.classList.add("editable");
  if (isEdited(scope, field)) node.classList.add("is-edited");

  original = baseOf(scope, field, original);
  const apply = (on) => {
    node.contentEditable = on ? "true" : "false";
    if (on) node.setAttribute("spellcheck", "true"); else node.removeAttribute("spellcheck");
    node.title = on ? "Click to edit — Esc to cancel" : "";
  };
  apply(editing);
  const off = onEditModeChange(apply);
  node.addEventListener("blur", () => {
    if (!editing) return;
    const val = plain ? node.textContent.trim() : node.innerHTML.trim();
    setText(scope, field, val, original);
    node.classList.toggle("is-edited", isEdited(scope, field));
    window.dispatchEvent(new CustomEvent("dv:edits"));
  });
  node.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { e.preventDefault(); node.blur(); }
    if (e.key === "Enter" && plain) { e.preventDefault(); node.blur(); }
  });
  return off;
}

/** Download every override as JSON, so edits can be baked into the build. */
export function exportEdits() {
  const blob = new Blob([JSON.stringify(store, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "data-visualization-edits.json";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export async function importEdits(file) {
  const txt = await file.text();
  const obj = JSON.parse(txt);
  if (obj && typeof obj === "object") { store = obj; persist(); }
}
