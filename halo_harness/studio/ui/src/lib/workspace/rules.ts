// The stage's rules (3.6.0.0 R0a, docs/STUDIO.md "Room"; Stage.tsx draws them): pure functions over a view's specs and its Layout.
//   R1  the main thing keeps >= 60 % of the stage: the open drawers together take at most the other 40 %
//   R2  a drawer is as wide as its content (`contentW`, 360-560 px), never a share of grid cells
//   R9  under 1440 px one drawer at a time; at 1440 and up one per side, the oldest closing when the room runs out
// A pack that declares its panels with grid cells (packs API 1.x) keeps working by the mapping rule: a panel with
// cells and no role is a right drawer whose contentW is its `w` columns x 60 px; `primary` is the main thing.
import { BP_WIDE, CELL_PX, DRAWER_MAX, DRAWER_MIN, MAIN_SHARE, type Layout, type PanelLayout, type PanelSpec, type Role, type Side } from "./types";

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export function roleOf(s: PanelSpec): Role {
  if (s.role) return s.role;
  return s.primary ? "main" : "drawer";
}

export function sideOf(s: PanelSpec): Side {
  return s.side === "left" ? "left" : "right";
}

/** A drawer's own width: its contentW, or a pack's `w` columns x 60 px, in 360-560. */
export function contentWOf(s: PanelSpec): number {
  return clamp(Math.round(s.contentW ?? (s.w ? s.w * CELL_PX : 420)), DRAWER_MIN, DRAWER_MAX);
}

/** The view's main thing (undefined: a view of drawers only, e.g. Local's Media over its page). */
export function mainOf(specs: PanelSpec[]): PanelSpec | undefined {
  return specs.find((s) => roleOf(s) === "main" && !s.optional);
}

/** The stage row's padding (each side) and the gap beside a drawer, px (workspace.css: var(--s-3)). */
export const STAGE_PAD = 12;

/** The widest `n` drawers may be together on a stage `stageW` px wide, its padding and their gaps counted (R1: the main
 *  thing keeps 60 % of the stage's width); never under one drawer's least. */
export function drawerRoom(stageW: number, n = 1): number {
  return Math.max(DRAWER_MIN, Math.floor(stageW * (1 - MAIN_SHARE)) - 2 * STAGE_PAD - STAGE_PAD * n);
}

/** A drawer's width on this stage: set by hand, else its contentW; never more than the drawers' room. */
export function drawerW(s: PanelSpec, p: PanelLayout | undefined, stageW: number): number {
  const want = clamp(Math.round(p?.width ?? contentWOf(s)), DRAWER_MIN, DRAWER_MAX);
  return stageW > 0 ? Math.min(want, drawerRoom(stageW)) : want;
}

function fresh(s: PanelSpec, collapsed: boolean): PanelLayout {
  return { collapsed, face: s.face ?? "detail", z: 0 };
}

/** The default: the main thing shown, every drawer and tab closed (nothing opens by itself, R0 house rule). */
export function defaultLayout(specs: PanelSpec[]): Layout {
  const out: Layout = {};
  for (const s of specs) if (!s.optional) out[s.id] = fresh(s, roleOf(s) === "drawer" ? !s.startOpen : roleOf(s) === "tab");
  return out;
}

/** A layout over today's specs: unknown ids dropped, new panels added closed, what `saved` had open kept open. */
export function merge(specs: PanelSpec[], saved: Layout | null): Layout {
  const out = defaultLayout(specs);
  if (!saved) return out;
  for (const s of specs) {
    const p = saved[s.id];
    if (!p) continue;
    out[s.id] = { ...(out[s.id] ?? fresh(s, true)), ...p };
  }
  return out;
}

/** `?open=all`: every panel of the view in it and open but the ones whose spec says `collapsed` (the drivers' door:
 *  each side's drawers, and the tabs on the right, stacked in one drawer per side). */
export function fullLayout(specs: PanelSpec[]): Layout {
  const out: Layout = {};
  for (const s of specs) if (!s.optional) out[s.id] = fresh(s, !!s.collapsed && roleOf(s) !== "main");
  return out;
}

const top = (l: Layout) => Object.values(l).reduce((m, p) => Math.max(m, p.z || 0), 0);

/** `id` shown: a drawer opens (closing what R1 / R9 say must close), a tab or the main thing becomes the one shown;
 *  `keep` (the full arrangement): nothing else closes. */
export function openIn(layout: Layout, specs: PanelSpec[], id: string, stageW: number, patch: Partial<PanelLayout> = {}, keep = false): Layout {
  const spec = specs.find((s) => s.id === id);
  if (!spec) return layout;
  const out: Layout = { ...layout, [id]: { ...(layout[id] ?? fresh(spec, true)), ...patch, collapsed: false, z: top(layout) + 1 } };
  const role = roleOf(spec);
  const inView = (s: PanelSpec) => !!out[s.id];
  if (keep || role === "dock") return out; // the full arrangement (`?open=all`): what is open stays open
  if (role !== "drawer") {
    for (const s of specs) if (s.id !== id && inView(s) && (roleOf(s) === "main" || roleOf(s) === "tab")) out[s.id] = { ...out[s.id], collapsed: true };
    return out;
  }
  const others = specs.filter((s) => s.id !== id && inView(s) && roleOf(s) === "drawer" && !out[s.id].collapsed);
  for (const s of others) if (sideOf(s) === sideOf(spec) || stageW < BP_WIDE) out[s.id] = { ...out[s.id], collapsed: true };
  // the oldest open drawer closes while the drawers together leave the main thing under 60 %
  const open = () => specs.filter((s) => inView(s) && roleOf(s) === "drawer" && !out[s.id].collapsed);
  while (stageW > 0 && open().length > 1 && open().reduce((t, s) => t + drawerW(s, out[s.id], 0), 0) > drawerRoom(stageW, open().length)) {
    const oldest = open().filter((s) => s.id !== id).sort((a, b) => (out[a.id].z || 0) - (out[b.id].z || 0))[0];
    if (!oldest) break;
    out[oldest.id] = { ...out[oldest.id], collapsed: true };
  }
  return out;
}

/** `id` put away: a drawer closes; a tab hands the stage back to the main thing; the main thing stays. */
export function closeIn(layout: Layout, specs: PanelSpec[], id: string): Layout {
  const spec = specs.find((s) => s.id === id);
  if (!spec || !layout[id]) return layout;
  const role = roleOf(spec);
  if (role === "main" || role === "dock") return layout;
  const out: Layout = { ...layout, [id]: { ...layout[id], collapsed: true } };
  if (role === "tab") {
    const main = mainOf(specs);
    if (main && out[main.id]) out[main.id] = { ...out[main.id], collapsed: false };
  }
  return out;
}

/** The panel shown in the main slot: a selected tab, else the main thing. */
export function shownMain(specs: PanelSpec[], layout: Layout): PanelSpec | undefined {
  const tab = specs.find((s) => roleOf(s) === "tab" && layout[s.id] && !layout[s.id].collapsed);
  return tab ?? mainOf(specs);
}

/** The open drawers on `side`, oldest first (one, except in the full arrangement). */
export function openDrawers(specs: PanelSpec[], layout: Layout, side?: Side): PanelSpec[] {
  return specs
    .filter((s) => roleOf(s) === "drawer" && layout[s.id] && !layout[s.id].collapsed && (!side || sideOf(s) === side))
    .sort((a, b) => (layout[a.id].z || 0) - (layout[b.id].z || 0));
}
