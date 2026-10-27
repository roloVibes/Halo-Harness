// Workspace persistence: one store per section holding its live Layout, saved
// to localStorage under `halo.studio.layout.<section>` ({v: 2, panels}) when
// the user changes it. A section the user never rearranged keeps no key, so
// its defaults follow the window size. `resetLayout` removes the key. A v1
// arrangement (3.0.3.0, when panels opened on their Glance face) keeps its
// places and sizes but not its faces, so every panel opens on its full face.
// A strip that opens (3.1.4.0 R1: a section may start panels as strips)
// pushes the grid panels it now covers down; nothing else moves. 3.2.2.0 R5:
// `arrangeLayout` (Arrange in the header's ... menu and the palette) puts the open panels
// back in the section's default rectangles and keeps them open as they are.
// 3.3.2.0 R3: while a section's arrangement is its quiet one (quiet.ts: the
// primary filling the stage, strips at the foot; nobody moved anything by
// hand), a strip that opens joins the column on the primary's right and a
// panel collapsed again gives its columns back to the primary.
import { createStore, writeLocal, type Store } from "../store";
import { arrange, defaultPanel, defaultRects, pushDown } from "./grid";
import { FULL_PAGE, isQuiet, quietReflow } from "./quiet";
import { ROW, type Layout, type PanelLayout, type PanelSpec } from "./types";

export const LAYOUT_PREFIX = "halo.studio.layout.";
const VERSION = 2;

/** `focus`: a one-shot request to move the keyboard focus to a panel; `active`: the panel the user is on (the ring). */
export type LayoutState = { layout: Layout | null; custom: boolean; focus: string; active: string };

const stores = new Map<string, Store<LayoutState>>();
const specsOf = new Map<string, PanelSpec[]>();

/** The Workspace says which specs a section draws (so a patch can lay the quiet arrangement out again). */
export function registerSpecs(section: string, specs: PanelSpec[]): void {
  specsOf.set(section, specs);
}

/** `next` laid out quietly again when `cur` was the quiet arrangement; null when the user's own arrangement rules. */
function requiet(section: string, cur: Layout, next: Layout): Layout | null {
  const specs = specsOf.get(section);
  const fill = fillOf(section);
  return specs && !FULL_PAGE && isQuiet(specs, fill, cur) ? quietReflow(specs, fill, next) : null;
}

export function layoutKey(section: string): string {
  return LAYOUT_PREFIX + section;
}

export function loadSaved(section: string): Layout | null {
  try {
    const raw = localStorage.getItem(layoutKey(section));
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || (data.v !== VERSION && data.v !== 1) || typeof data.panels !== "object") return null;
    const out: Layout = {};
    for (const [id, p] of Object.entries(data.panels as Record<string, Partial<PanelLayout>>)) {
      if (!p || ![p.x, p.y, p.w, p.h].every((n) => typeof n === "number" && isFinite(n))) continue;
      const kept = { ...p };
      if (data.v === 1) delete kept.face;
      out[id] = kept as PanelLayout;
    }
    return out;
  } catch {
    return null;
  }
}

export function layoutStore(section: string): Store<LayoutState> {
  let s = stores.get(section);
  if (!s) {
    s = createStore<LayoutState>({ layout: null, custom: loadSaved(section) !== null, focus: "", active: "" });
    stores.set(section, s);
  }
  return s;
}

/** Replace the section's layout; `save` (a user change) also persists it. */
export function setLayout(section: string, layout: Layout, save = true): void {
  const s = layoutStore(section);
  s.update(() => ({ layout, custom: s.get().custom || save }));
  if (save) writeLocal(layoutKey(section), JSON.stringify({ v: VERSION, panels: layout }));
}

export function patchPanel(section: string, id: string, patch: Partial<PanelLayout>, save = true): void {
  const cur = layoutStore(section).get().layout;
  if (!cur || !cur[id]) return;
  const next = { ...cur, [id]: { ...cur[id], ...patch } };
  const opened = cur[id].collapsed && !next[id].collapsed && !next[id].floating;
  const quiet = cur[id].collapsed !== next[id].collapsed || cur[id].floating !== next[id].floating ? requiet(section, cur, next) : null;
  setLayout(section, quiet || (opened ? pushDown(next, id) : next), save);
}

/** Forget the user's arrangement: the Workspace redraws the defaults. */
export function resetLayout(section: string): void {
  writeLocal(layoutKey(section), null);
  layoutStore(section).update(() => ({ layout: null, custom: false }));
}

/** The rows a section's workspace shows (Workspace.tsx's fillRows). */
function fillOf(section: string): number {
  const ws = document.querySelector<HTMLElement>(`.workspace[data-section="${section}"]`);
  return Math.max(0, Math.floor(((ws?.clientHeight || 624) - 24) / ROW));
}

/** Arrange: every panel open now in its default place and size; strips stay strips, faces stay, a floating one floats. */
export function arrangeLayout(section: string, specs: PanelSpec[]): void {
  const cur = layoutStore(section).get().layout;
  if (!cur) return;
  setLayout(section, defaultRects(specs, cur, fillOf(section), FULL_PAGE), true);
}

/** One panel back to its default place, size and face (the others make room). */
export function resetPanel(section: string, spec: PanelSpec): void {
  const cur = layoutStore(section).get().layout;
  if (!cur || !cur[spec.id]) return;
  const ws = document.querySelector<HTMLElement>(`.workspace[data-section="${section}"]`);
  const fill = Math.floor((ws?.clientHeight || 600) / ROW) - 3;
  setLayout(section, arrange({ ...cur, [spec.id]: { ...defaultPanel(spec, fill), z: cur[spec.id].z } }, spec.id));
}

export function focusPanel(section: string, id: string): void {
  layoutStore(section).update(() => ({ focus: id, active: id }));
}

/** The panel the user clicked or tabbed into: it carries the focus ring. */
export function activatePanel(section: string, id: string): void {
  layoutStore(section).update((s) => (s.active === id ? {} : { active: id }));
}

/** Open a panel and focus it; one not in the layout yet (an optional panel) is added below the
 *  others, or popped out over the grid with `float` (a section whose canvas fills the view). */
export function showPanel(section: string, spec: PanelSpec, float = false): void {
  const cur = layoutStore(section).get().layout;
  if (!cur) return;
  if (cur[spec.id]) patchPanel(section, spec.id, { collapsed: false }, false);
  else {
    const all = Object.values(cur);
    const bottom = all.reduce((m, p) => Math.max(m, p.y + p.h), 0);
    const top = all.reduce((m, p) => Math.max(m, p.z || 0), 0);
    const n = all.filter((p) => p.floating).length;
    const p = { ...defaultPanel({ ...spec, collapsed: false }, 60), y: bottom, face: "detail" as const };
    const placed = float ? { ...p, floating: true, fx: 64 + n * 32, fy: 48 + n * 32, fw: 520, fh: 440, z: top + 1 } : p;
    const next = { ...cur, [spec.id]: placed };
    setLayout(section, requiet(section, cur, next) || arrange(next, float ? undefined : spec.id), true);
  }
  focusPanel(section, spec.id);
}

/** Take an optional panel out of the layout again. */
export function hidePanel(section: string, id: string): void {
  const cur = layoutStore(section).get().layout;
  if (!cur || !cur[id]) return;
  const next = { ...cur };
  delete next[id];
  setLayout(section, requiet(section, cur, next) || arrange(next), true);
}
