// Grid math for the workspace: clamp and snap rects, apply a move/resize
// delta, make room for a moved panel (room.ts, 3.2.2.0 R5: its neighbours
// give up columns, trade places, or go down inside the visible rows) and
// compact everything upward (the panel being dragged stays where the pointer
// put it, or as near as the room it found allows). Pure functions.
import { makeRoom, type RoomOpts } from "./room";
import { COLS, MIN_H, MIN_W, ROW, STRIP_ROWS, type Gesture, type Layout, type PanelLayout, type PanelSpec, type Rect } from "./types";

export function minW(spec?: PanelSpec): number {
  return Math.max(MIN_W, spec?.minW ?? MIN_W);
}

export function minH(spec?: PanelSpec): number {
  return Math.max(MIN_H, spec?.minH ?? MIN_H);
}

export function clampRect(r: Rect, spec?: PanelSpec): Rect {
  const w = Math.min(COLS, Math.max(minW(spec), Math.round(r.w)));
  const h = Math.max(minH(spec), Math.round(r.h));
  const x = Math.min(COLS - w, Math.max(0, Math.round(r.x)));
  const y = Math.max(0, Math.round(r.y));
  return { x, y, w, h };
}

/** Rows a panel occupies on the grid (a collapsed one is a strip). */
export function effH(p: PanelLayout): number {
  return p.collapsed ? STRIP_ROWS : p.h;
}

function hits(a: PanelLayout, b: PanelLayout): boolean {
  return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + effH(b) && b.y < a.y + effH(a);
}

/** Apply a pointer delta (in cells / rows) for a gesture to a start rect. */
export function applyDelta(start: Rect, g: Gesture, dx: number, dy: number, spec?: PanelSpec): Rect {
  if (g === "move") return clampRect({ ...start, x: start.x + dx, y: start.y + dy }, spec);
  let { x, y, w, h } = start;
  const mw = minW(spec);
  const mh = minH(spec);
  if (g.includes("e")) w = Math.min(COLS - x, Math.max(mw, w + dx));
  if (g.includes("s")) h = Math.max(mh, h + dy);
  if (g.includes("w")) {
    const nx = Math.min(x + w - mw, Math.max(0, x + dx));
    w += x - nx;
    x = nx;
  }
  if (g.includes("n")) {
    const ny = Math.min(y + h - mh, Math.max(0, y + dy));
    h += y - ny;
    y = ny;
  }
  return { x, y, w, h };
}

/** Same for a floating panel, in px snapped to the 8 px row unit. */
export function applyDeltaPx(start: Rect, g: Gesture, dx: number, dy: number, bounds: { w: number; h: number }): Rect {
  const snap = (v: number) => Math.round(v / ROW) * ROW;
  const minWpx = 200;
  const minHpx = MIN_H * ROW;
  let { x, y, w, h } = start;
  if (g === "move") {
    x = Math.min(Math.max(0, bounds.w - 80), Math.max(0, snap(x + dx)));
    y = Math.max(0, snap(y + dy));
    return { x, y, w, h };
  }
  if (g.includes("e")) w = Math.max(minWpx, snap(w + dx));
  if (g.includes("s")) h = Math.max(minHpx, snap(h + dy));
  if (g.includes("w")) {
    const nx = Math.min(x + w - minWpx, Math.max(0, snap(x + dx)));
    w += x - nx;
    x = nx;
  }
  if (g.includes("n")) {
    const ny = Math.min(y + h - minHpx, Math.max(0, snap(y + dy)));
    h += y - ny;
    y = ny;
  }
  return { x, y, w, h };
}

function gridIds(layout: Layout): string[] {
  return Object.keys(layout)
    .filter((id) => !layout[id].floating)
    .sort((a, b) => layout[a].y - layout[b].y || layout[a].x - layout[b].x || (a < b ? -1 : 1));
}

/** Push every grid panel that overlaps `movedId` (and so on) below it. */
export function pushDown(layout: Layout, movedId: string): Layout {
  const out: Layout = { ...layout };
  const queue = [movedId];
  let guard = 0;
  while (queue.length && guard++ < 500) {
    const id = queue.shift()!;
    const a = out[id];
    if (!a || a.floating) continue;
    for (const other of gridIds(out)) {
      if (other === id || other === movedId) continue;
      const b = out[other];
      if (hits(a, b)) {
        out[other] = { ...b, y: a.y + effH(a) };
        queue.push(other);
      }
    }
  }
  return out;
}

/** Move every grid panel up as far as it goes; `pinnedId` stays put. */
export function compact(layout: Layout, pinnedId?: string): Layout {
  const out: Layout = { ...layout };
  const placed: PanelLayout[] = [];
  if (pinnedId && out[pinnedId] && !out[pinnedId].floating) placed.push(out[pinnedId]);
  for (const id of gridIds(out)) {
    if (id === pinnedId) continue;
    let p = { ...out[id], y: 0 };
    while (placed.some((q) => hits(p, q))) {
      const blocker = placed.filter((q) => hits(p, q)).reduce((m, q) => Math.max(m, q.y + effH(q)), 0);
      p = { ...p, y: blocker };
    }
    out[id] = p;
    placed.push(p);
  }
  return out;
}

/** Make room, then compact: the arrangement after `movedId` changed (`opts`: the visible rows, its old rect, the specs). */
export function arrange(layout: Layout, movedId?: string, pinned = false, opts?: RoomOpts): Layout {
  const roomy = movedId ? (opts ? makeRoom(layout, movedId, opts) : pushDown(layout, movedId)) : layout;
  return compact(roomy, pinned ? movedId : undefined);
}

/** Arrange (the rail, the palette): the section's default rectangles for the panels open now; strips stay strips, floats float. */
export function defaultRects(specs: PanelSpec[], layout: Layout, fillRows: number): Layout {
  const out: Layout = {};
  for (const s of specs) {
    const p = layout[s.id];
    if (!p) continue;
    const d = defaultPanel(s, fillRows);
    out[s.id] = p.floating ? p : { ...p, x: d.x, y: d.y, w: d.w, h: d.h };
  }
  for (const id of Object.keys(layout)) if (!out[id]) out[id] = layout[id];
  return compact(out);
}

export function defaultPanel(spec: PanelSpec, fillRows: number): PanelLayout {
  const h = spec.h > 0 ? spec.h : Math.max(minH(spec), fillRows - spec.y + spec.h); // 3.1.5.0 R3: h < 0 leaves -h rows below
  const r = clampRect({ x: spec.x, y: spec.y, w: spec.w, h }, spec);
  return { ...r, collapsed: !!spec.collapsed, floating: false, fx: 48, fy: 48, fw: 480, fh: 320, face: spec.face ?? "detail", z: 0 };
}

export function defaultLayout(specs: PanelSpec[], fillRows: number): Layout {
  const out: Layout = {};
  for (const s of specs) if (!s.optional) out[s.id] = defaultPanel(s, fillRows);
  return arrange(out);
}

/** A saved layout over today's specs: unknown ids dropped, new panels added at their defaults. */
export function merge(specs: PanelSpec[], saved: Layout | null, fillRows: number): Layout {
  const base = defaultLayout(specs, fillRows);
  if (!saved) return base;
  const out: Layout = {};
  for (const s of specs) {
    const p = saved[s.id];
    const d = base[s.id] || defaultPanel(s, fillRows);
    if (p) out[s.id] = { ...d, ...p, ...clampRect(p, s) };
    else if (!s.optional) out[s.id] = d;
  }
  return arrange(out);
}

/** `?open=a,b`: those panels open and go to the top rows, in their columns, ahead of the rest. */
export function openFirst(layout: Layout, ids: string[]): Layout {
  const hit = ids.filter((id) => layout[id]);
  if (!hit.length) return layout;
  const out: Layout = { ...layout };
  for (const id of hit) out[id] = { ...out[id], collapsed: false, face: "detail", y: -1 };
  return compact(out);
}

/** Rows the grid needs (the lowest panel's bottom). */
export function usedRows(layout: Layout): number {
  return Object.values(layout).reduce((m, p) => (p.floating ? m : Math.max(m, p.y + effH(p))), 0);
}
