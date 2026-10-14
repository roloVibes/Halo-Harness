// Workspace persistence: one store per section holding its live Layout, saved
// to localStorage under `halo.studio.layout.<section>` ({v: 1, panels}) when
// the user changes it. A section the user never rearranged keeps no key, so
// its defaults follow the window size. `resetLayout` removes the key.
import { createStore, writeLocal, type Store } from "../store";
import type { Layout, PanelLayout } from "./types";

export const LAYOUT_PREFIX = "halo.studio.layout.";
const VERSION = 1;

export type LayoutState = { layout: Layout | null; custom: boolean; focus: string };

const stores = new Map<string, Store<LayoutState>>();

export function layoutKey(section: string): string {
  return LAYOUT_PREFIX + section;
}

export function loadSaved(section: string): Layout | null {
  try {
    const raw = localStorage.getItem(layoutKey(section));
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || data.v !== VERSION || typeof data.panels !== "object") return null;
    const out: Layout = {};
    for (const [id, p] of Object.entries(data.panels as Record<string, Partial<PanelLayout>>)) {
      if (p && [p.x, p.y, p.w, p.h].every((n) => typeof n === "number" && isFinite(n))) out[id] = p as PanelLayout;
    }
    return out;
  } catch {
    return null;
  }
}

export function layoutStore(section: string): Store<LayoutState> {
  let s = stores.get(section);
  if (!s) {
    s = createStore<LayoutState>({ layout: null, custom: loadSaved(section) !== null, focus: "" });
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
  setLayout(section, { ...cur, [id]: { ...cur[id], ...patch } }, save);
}

/** Forget the user's arrangement: the Workspace redraws the defaults. */
export function resetLayout(section: string): void {
  writeLocal(layoutKey(section), null);
  layoutStore(section).update(() => ({ layout: null, custom: false }));
}

export function focusPanel(section: string, id: string): void {
  layoutStore(section).update(() => ({ focus: id }));
}
