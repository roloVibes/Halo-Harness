// Workspace persistence (3.6.0.0 R0a, v3): one store per section holding its live Layout. What is kept in
// localStorage under `halo.studio.layout.<section>` is only what a person chose: the drawers open, a drawer's width
// set by hand, the tab shown, the optional panels added -- `{v: 3, lv, open, widths, tab, added}`. Opening a drawer is
// not a "custom layout" (R10); `custom` is true only once a width was set by hand. `lv` is the view's layout version
// (Workspace's `version`): a saved view of an older version is kept and the view says so once ("the layout changed":
// use the new one, or keep mine); a v1 / v2 arrangement of the old grid is dropped, with the same note once.
import { createStore, writeLocal, type Store } from "../store";
import { FULL_PAGE } from "./query";
import { closeIn, merge, openIn, roleOf } from "./rules";
import type { Layout, PanelLayout, PanelSpec } from "./types";

export const LAYOUT_PREFIX = "halo.studio.layout.";
const VERSION = 3;

/** `focus`: a one-shot request to move the keyboard focus to a panel; `active`: the panel the user is on (the ring);
 *  `note`: the one-time layout note ("changed": a newer default exists, yours is kept; "dropped": an old grid layout went). */
export type LayoutState = { layout: Layout | null; custom: boolean; focus: string; active: string; note: "" | "changed" | "dropped" };
export type Saved = { open: string[]; widths: Record<string, number>; tab: string; added: string[]; lv: number };

const stores = new Map<string, Store<LayoutState>>();
const specsOf = new Map<string, PanelSpec[]>();
const versions = new Map<string, number>();

/** The Workspace says which specs a section draws, and its layout version. */
export function registerSpecs(section: string, specs: PanelSpec[], version = 1): void {
  specsOf.set(section, specs);
  versions.set(section, version);
}

/** 3.3.13.0 R2: the specs a section's Workspace drew last (a pack's page draws its own: the Inspector finds them here). */
export function specsFor(section: string): PanelSpec[] | undefined {
  return specsOf.get(section);
}

export function layoutKey(section: string): string {
  return LAYOUT_PREFIX + section;
}

function readRaw(section: string): unknown {
  try {
    const raw = localStorage.getItem(layoutKey(section));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** The saved v3 record, or null (none, unreadable, or an old grid arrangement: `oldGrid` says which). */
export function loadSaved(section: string): Saved | null {
  const d = readRaw(section) as Partial<Saved> & { v?: number } | null;
  if (!d || d.v !== VERSION) return null;
  const list = (x: unknown) => (Array.isArray(x) ? x.filter((v): v is string => typeof v === "string") : []);
  const widths: Record<string, number> = {};
  for (const [k, v] of Object.entries(d.widths && typeof d.widths === "object" ? d.widths : {})) if (typeof v === "number" && isFinite(v)) widths[k] = v;
  return { open: list(d.open), widths, tab: typeof d.tab === "string" ? d.tab : "", added: list(d.added), lv: typeof d.lv === "number" ? d.lv : 1 };
}

function oldGrid(section: string): boolean {
  const d = readRaw(section) as { v?: number } | null;
  return !!d && (d.v === 1 || d.v === 2);
}

/** The saved record as a Layout over `specs` (null: nothing saved). */
export function savedLayout(section: string, specs: PanelSpec[]): Layout | null {
  const s = loadSaved(section);
  if (!s) return null;
  const out: Layout = {};
  for (const spec of specs) {
    const added = !spec.optional || s.added.includes(spec.id);
    if (!added) continue;
    const role = roleOf(spec);
    const open = role === "main" ? !s.tab || !specs.some((x) => x.id === s.tab) : role === "tab" ? s.tab === spec.id : s.open.includes(spec.id);
    out[spec.id] = { collapsed: !open, face: spec.face ?? "detail", z: open ? s.open.indexOf(spec.id) + 1 : 0, ...(s.widths[spec.id] ? { width: s.widths[spec.id] } : {}) };
  }
  return out;
}

function toSaved(section: string, layout: Layout): Saved {
  const specs = specsOf.get(section) || [];
  const roleOfId = (id: string) => {
    const s = specs.find((x) => x.id === id);
    return s ? roleOf(s) : "drawer";
  };
  const ids = Object.keys(layout);
  const open = ids.filter((id) => roleOfId(id) === "drawer" && !layout[id].collapsed).sort((a, b) => (layout[a].z || 0) - (layout[b].z || 0));
  const widths: Record<string, number> = {};
  for (const id of ids) if (layout[id].width) widths[id] = layout[id].width as number;
  const tab = ids.find((id) => roleOfId(id) === "tab" && !layout[id].collapsed) || "";
  const added = ids.filter((id) => specs.find((s) => s.id === id)?.optional);
  return { open, widths, tab, added, lv: versions.get(section) || 1 };
}

export function layoutStore(section: string): Store<LayoutState> {
  let s = stores.get(section);
  if (!s) {
    s = createStore<LayoutState>({ layout: null, custom: Object.keys(loadSaved(section)?.widths || {}).length > 0, focus: "", active: "", note: "" });
    stores.set(section, s);
  }
  return s;
}

/** The note a first draw shows: an old grid arrangement is dropped now; a saved view of an older version is kept and
 *  re-saved at today's version (so the note shows once). */
export function takeNote(section: string): LayoutState["note"] {
  if (oldGrid(section)) {
    writeLocal(layoutKey(section), null);
    return "dropped";
  }
  const s = loadSaved(section);
  const lv = versions.get(section) || 1;
  if (s && s.lv < lv) {
    writeLocal(layoutKey(section), JSON.stringify({ v: VERSION, ...s, lv }));
    return "changed";
  }
  return "";
}

/** Run `go` once the section's workspace has laid out (at once when it has); gives up after `ms`. */
export function whenLaidOut(section: string, go: () => void, ms = 30000): void {
  const s = layoutStore(section);
  if (s.get().layout) return go();
  const stop = s.subscribe(() => {
    if (!s.get().layout) return;
    stop();
    window.clearTimeout(timer);
    go();
  });
  const timer = window.setTimeout(stop, ms);
}

/** Replace the section's layout; `save` also persists what a person chose (open drawers, widths, the tab). */
export function setLayout(section: string, layout: Layout, save = true): void {
  const s = layoutStore(section);
  const custom = Object.values(layout).some((p) => !!p.width);
  s.update(() => ({ layout, custom }));
  if (save) writeLocal(layoutKey(section), JSON.stringify({ v: VERSION, ...toSaved(section, layout) }));
}

/** The stage's width now (drawers make room by it). */
export function stageWidth(section: string): number {
  const el = document.querySelector<HTMLElement>(`.workspace[data-section="${section}"]`);
  return el?.clientWidth || window.innerWidth;
}

/** Change one panel: `collapsed: false` opens it (a drawer by the stage's rules, a tab shown), `true` puts it away. */
export function patchPanel(section: string, id: string, patch: Partial<PanelLayout>, save = true): void {
  const cur = layoutStore(section).get().layout;
  const specs = specsOf.get(section) || [];
  if (!cur || !cur[id]) return;
  const { collapsed, ...rest } = patch;
  let next: Layout = { ...cur, [id]: { ...cur[id], ...rest } };
  if (collapsed === false) next = openIn(next, specs, id, stageWidth(section), {}, FULL_PAGE);
  else if (collapsed === true) next = closeIn(next, specs, id);
  setLayout(section, next, save);
}

/** Forget the person's choices: every drawer closed, the main thing shown, widths back to their content's. */
export function resetLayout(section: string): void {
  writeLocal(layoutKey(section), null);
  layoutStore(section).update(() => ({ layout: null, custom: false, note: "" }));
}

/** The one-time note answered: "use the new one" forgets the saved view; "keep mine" just closes the note. */
export function answerNote(section: string, useNew: boolean): void {
  if (useNew) resetLayout(section);
  layoutStore(section).update(() => ({ note: "" }));
}

/** One drawer back to its content's width. */
export function resetPanel(section: string, spec: PanelSpec): void {
  const cur = layoutStore(section).get().layout;
  if (!cur || !cur[spec.id]) return;
  const p = { ...cur[spec.id] };
  delete p.width;
  setLayout(section, { ...cur, [spec.id]: p });
}

export function focusPanel(section: string, id: string): void {
  layoutStore(section).update(() => ({ focus: id, active: id }));
}

/** The panel the user clicked or tabbed into: it carries the focus ring. */
export function activatePanel(section: string, id: string): void {
  layoutStore(section).update((s) => (s.active === id ? {} : { active: id }));
}

/** Open a panel and focus it; an optional panel not in the view yet is added first. (`_float` is the 3.3 grid's
 *  "pop it out over the page"; a drawer is what that is now.) */
export function showPanel(section: string, spec: PanelSpec, _float = false): void {
  const cur = layoutStore(section).get().layout;
  if (!cur) return;
  const base = cur[spec.id] ? cur : { ...cur, [spec.id]: { collapsed: true, face: spec.face ?? "detail", z: 0 } };
  const specs = specsOf.get(section) || [];
  setLayout(section, openIn(base, specs.some((s) => s.id === spec.id) ? specs : [...specs, spec], spec.id, stageWidth(section), {}, FULL_PAGE), true);
  focusPanel(section, spec.id);
}

/** Take an optional panel out of the view again (a tab hands the stage back to the main thing). */
export function hidePanel(section: string, id: string): void {
  const cur = layoutStore(section).get().layout;
  if (!cur || !cur[id]) return;
  const next = { ...closeIn(cur, specsOf.get(section) || [], id) };
  delete next[id];
  setLayout(section, next, true);
}

export { merge };
