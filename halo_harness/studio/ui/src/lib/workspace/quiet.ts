// "One thing per section" (Halo 3.3.2.0 R3; the owner, 2026-10-27: "the visuals in studio are too cluttered").
// A section whose specs name a `primary` panel opens on it: the primary fills the stage from the top, every
// other panel of the default arrangement is a strip at the foot (one or two rows, side by side, each at
// least its minW wide). A strip that opens joins the column on the right of the primary (as wide as the
// widest panel open there, at most half the stage; the panels in it share its height, top to bottom in the
// section's order), the primary giving up those columns; a panel collapsed again gives them back.
// `quietLayout` lays all of that out from what is open, stripped or floating now, so the default, Arrange and
// a strip opening on an untouched arrangement share one rule. Pure functions.
import { COLS, MIN_H, MIN_W, STRIP_ROWS, type Layout, type PanelLayout, type PanelSpec } from "./types";

/** `?open=all`: this page draws every panel in its spec's place (the arrangement before 3.3.2.0; a link, a capture). */
export const FULL_PAGE = typeof location !== "undefined" && /[?&]open=(?:[\w-]+,)*all(?:[,&#]|$)/.test(location.search);

const SIDE_MAX = 12; // the side column's widest (half the 24 columns)

const mw = (s: PanelSpec) => Math.max(MIN_W, s.minW ?? MIN_W);
const mh = (s: PanelSpec) => Math.max(MIN_H, s.minH ?? MIN_H);

/** The section's one thing (undefined: the section keeps its full arrangement). */
export function primaryOf(specs: PanelSpec[]): PanelSpec | undefined {
  return specs.find((s) => s.primary && !s.optional);
}

/** A row's members side by side across the 24 columns: even widths, the spare columns one each from the left. */
function spread(n: number): number[] {
  const base = Math.floor(COLS / n);
  const spare = COLS - base * n;
  return Array.from({ length: n }, (_, i) => base + (i < spare ? 1 : 0));
}

/** Strips in rows: as many per row as fit while every one keeps at least its minW (six at most). */
function rowsOf(members: PanelSpec[]): PanelSpec[][] {
  if (!members.length) return [];
  const widest = members.reduce((m, s) => Math.max(m, mw(s)), MIN_W);
  let per = Math.min(members.length, 6);
  while (per > 1 && Math.floor(COLS / per) < widest) per--;
  const out: PanelSpec[][] = [];
  for (let i = 0; i < members.length; i += per) out.push(members.slice(i, i + per));
  return out;
}

function base(s: PanelSpec, prev?: PanelLayout): PanelLayout {
  return prev
    ? { ...prev }
    : { x: 0, y: 0, w: COLS, h: MIN_H, collapsed: false, floating: false, fx: 48, fy: 48, fw: 480, fh: 320, face: s.face ?? "detail", z: 0 };
}

/**
 * The quiet arrangement of `ids` (in spec order): `strip(id)` says which are strips; floating panels of `prev`
 * stay where they float. The primary (else the first open panel) fills what the side column and the strips leave.
 */
export function quietLayout(specs: PanelSpec[], fillRows: number, ids: Set<string>, strip: (id: string) => boolean, prev: Layout = {}): Layout {
  const out: Layout = {};
  const grid: PanelSpec[] = [];
  for (const s of specs) {
    if (!ids.has(s.id)) continue;
    if (prev[s.id]?.floating) out[s.id] = prev[s.id];
    else grid.push(s);
  }
  const prim = primaryOf(specs);
  const strips = grid.filter((s) => strip(s.id));
  const open = grid.filter((s) => !strip(s.id));
  const filler = open.find((s) => s === prim) ?? open[0];
  const side = open.filter((s) => s !== filler);
  const stripRows = rowsOf(strips);
  const free = Math.max(MIN_H, fillRows - stripRows.length * STRIP_ROWS);
  let sideW = 0;
  if (side.length && filler) {
    const need = Math.max(...side.map(mw)); // every panel in the column keeps its minW
    const want = Math.max(need, ...side.map((s) => s.w)); // as wide as the widest spec, at most SIDE_MAX
    sideW = Math.min(Math.max(need, Math.min(want, SIDE_MAX)), COLS - mw(filler));
  }
  let bottom = 0;
  if (filler) {
    const h = Math.max(mh(filler), free);
    out[filler.id] = { ...base(filler, prev[filler.id]), x: 0, y: 0, w: COLS - sideW, h, collapsed: false, floating: false };
    bottom = h;
  }
  let y = 0;
  side.forEach((s, i) => {
    const share = Math.floor(free / side.length) + (i === side.length - 1 ? free % side.length : 0);
    const h = Math.max(mh(s), share);
    out[s.id] = { ...base(s, prev[s.id]), x: COLS - sideW, y, w: sideW, h, collapsed: false, floating: false };
    y += h;
  });
  bottom = Math.max(bottom, y);
  if (!open.length) bottom = Math.max(0, fillRows - stripRows.length * STRIP_ROWS);
  for (const row of stripRows) {
    let x = 0;
    spread(row.length).forEach((w, i) => {
      const s = row[i];
      const h = Math.max(mh(s), s.h > 0 ? s.h : 24); // what it opens to in your own arrangement
      out[s.id] = { ...base(s, prev[s.id]), x, y: bottom, w, h, collapsed: true, floating: false };
      x += w;
    });
    bottom += STRIP_ROWS;
  }
  return out;
}

/** The section's default when it has a primary: the primary open, every other non-optional panel a strip. */
export function quietDefault(specs: PanelSpec[], fillRows: number): Layout | null {
  const prim = primaryOf(specs);
  if (!prim) return null;
  const ids = new Set(specs.filter((s) => !s.optional).map((s) => s.id));
  return quietLayout(specs, fillRows, ids, (id) => id !== prim.id);
}

/** The same panels, open / strip / floating as they are in `cur`, laid out quietly again. */
export function quietReflow(specs: PanelSpec[], fillRows: number, cur: Layout): Layout {
  return quietLayout(specs, fillRows, new Set(Object.keys(cur)), (id) => !!cur[id]?.collapsed, cur);
}

/** True while `cur` is the quiet arrangement of what it holds (nobody moved or resized anything by hand). */
export function isQuiet(specs: PanelSpec[], fillRows: number, cur: Layout): boolean {
  if (!primaryOf(specs) || !fillRows) return false;
  const q = quietReflow(specs, fillRows, cur);
  return Object.keys(cur).every((id) => {
    const a = cur[id], b = q[id];
    if (!b) return false;
    if (a.floating) return true;
    return a.x === b.x && a.y === b.y && a.w === b.w && (a.collapsed || a.h === b.h);
  });
}
