// How the workspace grid makes room for a moved or resized panel (Halo
// 3.2.2.0 R5; the owner: "Moving one block should shrink the ones next to
// them without things disappearing"). A panel that lands on another: the
// neighbour gives up columns on the side facing it, down to its minW, and
// the moved panel takes what is left; two panels in the same columns (both
// full width among them) trade places, the neighbour taking the moved
// panel's old rectangle; only when neither fits does the neighbour go down,
// and never below the visible rows (`rows`, the workspace's fill height). An
// edge or corner resize is a splitter: the panel on that edge shrinks or
// grows by the same columns or rows, down to its minW / minH. Pure functions
// over a Layout; grid.ts's `arrange` calls `makeRoom` before it compacts.
import { bottom, hits, right, splitResize, type Box, type Edge } from "../geometry";
import { COLS, MIN_H, MIN_W, STRIP_ROWS, type Gesture, type Layout, type PanelLayout, type PanelSpec, type Rect } from "./types";

export type RoomOpts = {
  /** The visible rows (0 or absent: no limit). */
  rows?: number;
  /** The moved panel's rectangle before the gesture: a neighbour in its columns may take it. */
  from?: Rect;
  specs?: PanelSpec[];
};

const effH = (p: PanelLayout) => (p.collapsed ? STRIP_ROWS : p.h);
const box = (p: PanelLayout): Box => ({ x: p.x, y: p.y, w: p.w, h: effH(p) });
const spec = (o: RoomOpts, id: string) => o.specs?.find((s) => s.id === id);
const mw = (o: RoomOpts, id: string) => Math.max(MIN_W, spec(o, id)?.minW ?? MIN_W);
const mh = (o: RoomOpts, id: string, p: PanelLayout) => (p.collapsed ? STRIP_ROWS : Math.max(MIN_H, spec(o, id)?.minH ?? MIN_H));
const gridIds = (l: Layout) => Object.keys(l).filter((k) => !l[k].floating);
const center = (p: PanelLayout) => p.x + p.w / 2;

/** b beside a: b gives up columns on the side facing a (keeping its far edge), a takes what is left; null when it does not fit. */
function side(a: PanelLayout, b: PanelLayout, minA: number, minB: number): [PanelLayout, PanelLayout] | null {
  if (center(b) < center(a)) {
    const edge = Math.max(b.x + minB, a.x); // b keeps its left edge
    const nb = { ...b, w: edge - b.x };
    const na = { ...a, x: edge, w: Math.max(minA, right(a) - edge) };
    return right(na) <= COLS ? [na, nb] : null;
  }
  const edge = Math.min(right(b) - minB, right(a)); // b keeps its right edge
  const nb = { ...b, x: edge, w: right(b) - edge };
  const w = Math.max(minA, edge - a.x);
  const na = { ...a, x: edge - w, w };
  return na.x >= 0 ? [na, nb] : null;
}

/** b under a, shorter down to its minH so it ends by `rows`; a gives up rows when even that does not fit. */
function down(a: PanelLayout, b: PanelLayout, minA: number, minB: number, rows: number): [PanelLayout, PanelLayout] {
  let na = a;
  let y = a.y + effH(a);
  if (rows && !b.collapsed && y + minB > rows && !a.collapsed && a.h > minA) {
    na = { ...a, h: Math.max(minA, rows - minB - a.y) };
    y = na.y + na.h;
  }
  const h = b.collapsed ? b.h : rows && y + b.h > rows ? Math.max(minB, rows - y) : b.h;
  return [na, { ...b, y, h }];
}

/** The layout after `id` landed where it is: every panel it overlaps steps aside, sideways first. */
export function makeRoom(layout: Layout, id: string, o: RoomOpts = {}): Layout {
  const out: Layout = { ...layout };
  const rows = o.rows || 0;
  if (!out[id] || out[id].floating) return out;
  if (rows && out[id].y + effH(out[id]) > rows) out[id] = { ...out[id], y: Math.max(0, rows - effH(out[id])) };
  let from = o.from; // taken once: the first neighbour that trades places has it
  for (let pass = 0; pass < 12; pass++) {
    const a = out[id];
    const hit = gridIds(out).filter((k) => k !== id && hits(box(a), box(out[k])));
    if (!hit.length) break;
    const k = hit[0];
    const b = out[k];
    const minA = mw(o, id), minB = mw(o, k);
    const sameCols = a.x === b.x && a.w === b.w;
    const s = sameCols ? null : side(a, b, minA, minB);
    if (s && !gridIds(out).some((q) => q !== id && q !== k && hits(box(s[0]), box(out[q])) && !hits(box(a), box(out[q])))) {
      out[id] = s[0];
      out[k] = s[1];
      continue;
    }
    // trade places: b takes a's old rectangle, else (a moved down its own column) a's old top with its own size
    const trades = from ? [{ ...b, x: from.x, y: from.y, w: from.w, h: b.collapsed ? b.h : from.h }, { ...b, x: from.x, y: from.y, w: from.w }] : [];
    const swapped = trades.find((t) => !hits(box(a), box(t)) && (!rows || t.y + effH(t) <= rows));
    if (swapped) {
      out[k] = swapped;
      from = undefined;
      continue;
    }
    const [na, nb] = down(a, b, mh(o, id, a), mh(o, k, b), rows);
    out[id] = na;
    out[k] = nb;
  }
  return cascade(out, id, o);
}

/** A panel pushed onto another moves that one down too (inside the visible rows when it can). */
function cascade(layout: Layout, id: string, o: RoomOpts): Layout {
  const out: Layout = { ...layout };
  const rows = o.rows || 0;
  for (let guard = 0; guard < 64; guard++) {
    const ids = gridIds(out).sort((p, q) => out[p].y - out[q].y);
    let pair: [string, string] | null = null;
    for (const p of ids) for (const q of ids) if (!pair && p !== q && q !== id && out[p].y <= out[q].y && hits(box(out[p]), box(out[q]))) pair = [p, q];
    if (!pair) break;
    const [p, q] = pair;
    out[q] = down(out[p], out[q], mh(o, p, out[p]), mh(o, q, out[q]), rows)[1];
  }
  return out;
}

/** The neighbours of `p0` on `edge`: grid panels that touch that edge and share its rows (or columns). */
function neighbours(layout: Layout, id: string, p0: PanelLayout, edge: Edge): string[] {
  return gridIds(layout).filter((k) => {
    if (k === id) return false;
    const b = layout[k];
    const rowsShared = b.y < bottom(box(p0)) && p0.y < b.y + effH(b);
    const colsShared = b.x < right(p0) && p0.x < right(b);
    if (edge === "e") return b.x === right(p0) && rowsShared;
    if (edge === "w") return right(b) === p0.x && rowsShared;
    if (b.collapsed) return false;
    if (edge === "s") return b.y === p0.y + effH(p0) && colsShared;
    return b.y + effH(b) === p0.y && colsShared;
  });
}

/** A resize gesture as a splitter: `r` is the resized rectangle; the panels on the moved edges follow it. */
export function splitEdges(layout: Layout, id: string, g: Gesture, p0: PanelLayout, r: Rect, o: RoomOpts = {}): Layout {
  const out: Layout = { ...layout };
  let a: PanelLayout = { ...p0, ...r };
  const deltas: [Edge, number][] = [];
  if (g.includes("e")) deltas.push(["e", right(r) - right(p0)]);
  if (g.includes("w")) deltas.push(["w", r.x - p0.x]);
  if (!p0.collapsed && g.includes("s")) deltas.push(["s", r.y + r.h - (p0.y + p0.h)]);
  if (!p0.collapsed && g.includes("n")) deltas.push(["n", r.y - p0.y]);
  for (const [edge, delta] of deltas) {
    const ns = neighbours(layout, id, p0, edge);
    if (!ns.length || !delta) continue;
    const minA = { w: mw(o, id), h: mh(o, id, p0) };
    // the delta every neighbour can follow
    let d = delta;
    for (const k of ns) d = splitResize(box(p0), box(layout[k]), edge, d, minA, { w: mw(o, k), h: mh(o, k, layout[k]) }).delta;
    for (const k of ns) {
      const s = splitResize(box(p0), box(layout[k]), edge, d, minA, { w: mw(o, k), h: mh(o, k, layout[k]) });
      out[k] = { ...layout[k], x: s.b.x, y: s.b.y, w: s.b.w, h: layout[k].collapsed ? layout[k].h : s.b.h };
    }
    const s = splitResize(box(p0), box(layout[ns[0]]), edge, d, minA, { w: 0, h: 0 }).a;
    a = edge === "e" || edge === "w" ? { ...a, x: s.x, w: s.w } : { ...a, y: s.y, h: s.h };
  }
  out[id] = a;
  return out;
}
