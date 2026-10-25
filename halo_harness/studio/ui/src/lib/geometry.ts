// Rectangle math shared by the workspace grid (lib/workspace/room.ts, in
// cells and rows) and the canvases (the Roles cards in their tier boxes,
// Design's artboards, in px). Halo 3.2.2.0 R5 "the canvas makes room": a box
// that lands on another never covers it. `nudgeApart` moves what the moved box
// overlaps: sideways first (a resizable box gives up width on the side facing
// the moved one, down to its minimum; a fixed-size one slides), then it trades
// places with the moved box (takes its old spot), then it goes down -- never
// past the bounds. `placeBeside` finds a free spot next to a box, and
// `splitResize` turns an edge drag into a splitter between two neighbours.
// Pure functions, no DOM.

export type Box = { x: number; y: number; w: number; h: number };
export type Size = { w: number; h: number };
export type Edge = "n" | "s" | "e" | "w";

export type Room = {
  /** The smallest a nudged box may get (a fixed-size card: its own size). */
  minW: number;
  minH: number;
  /** Space kept between the moved box and what steps aside. */
  gap?: number;
  /** Where the moved box was before: what it overlaps may take that spot. */
  from?: Box;
  /** A trade of places takes the old box's size too (the grid), else only its spot (a card). */
  swapSize?: boolean;
};

export const right = (b: Box) => b.x + b.w;
export const bottom = (b: Box) => b.y + b.h;
const cx = (b: Box) => b.x + b.w / 2;

/** True when the two boxes share any area (touching edges do not count). */
export function hits(a: Box, b: Box): boolean {
  return a.x < right(b) && b.x < right(a) && a.y < bottom(b) && b.y < bottom(a);
}

/** True when `b` lies wholly inside `bounds`. */
export function within(b: Box, bounds: Box): boolean {
  return b.x >= bounds.x - 0.5 && b.y >= bounds.y - 0.5 && right(b) <= right(bounds) + 0.5 && bottom(b) <= bottom(bounds) + 0.5;
}

/** The smallest box around both. */
export function union(a: Box, b: Box): Box {
  const x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
  return { x, y, w: Math.max(right(a), right(b)) - x, h: Math.max(bottom(a), bottom(b)) - y };
}

/** Every pair of keys whose boxes overlap. */
export function overlaps(boxes: Record<string, Box>): [string, string][] {
  const ids = Object.keys(boxes);
  const out: [string, string][] = [];
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) if (hits(boxes[ids[i]], boxes[ids[j]])) out.push([ids[i], ids[j]]);
  return out;
}

/** `b` stepped off `p` to one side: it keeps its far edge and gives up width down to `minW`, else slides. */
function sideways(p: Box, b: Box, toRight: boolean, bounds: Box, room: Room): Box | null {
  const gap = room.gap || 0;
  if (toRight) {
    const x = right(p) + gap;
    const r = Math.min(right(bounds), Math.max(right(b), x + room.minW));
    return r - x >= room.minW - 0.01 ? { ...b, x, w: Math.min(b.w, r - x) } : null;
  }
  const r = p.x - gap;
  const x = Math.max(bounds.x, Math.min(b.x, r - room.minW));
  return r - x >= room.minW - 0.01 ? { ...b, x, w: Math.min(b.w, r - x) } : null;
}

/** `b` under `p`: shorter down to `minH` when it would pass the bounds' bottom, never past it. */
function below(p: Box, b: Box, bounds: Box, room: Room): Box {
  const y = bottom(p) + (room.gap || 0);
  let h = b.h;
  if (y + h > bottom(bounds)) h = Math.max(Math.min(b.h, room.minH), bottom(bounds) - y);
  return { ...b, y: Math.max(bounds.y, Math.min(y, bottom(bounds) - h)), h };
}

/** The spots `b` may take, best first, when `p` lands on it. */
function candidates(p: Box, b: Box, first: boolean, bounds: Box, room: Room): Box[] {
  const toRight = cx(b) >= cx(p);
  const out: Box[] = [];
  for (const side of [toRight, !toRight]) {
    const s = sideways(p, b, side, bounds, room);
    if (s) out.push(s);
  }
  if (first && room.from) out.push(room.swapSize ? { ...room.from } : { ...b, x: room.from.x, y: room.from.y });
  out.push(below(p, b, bounds, room));
  return out;
}

/**
 * The others after `moved` landed among them: each box it overlaps steps aside (and so on, for a box that
 * then overlaps another), the moved box itself never moves. A spot that overlaps nothing wins; else the first
 * that keeps clear of the moved box; the last resort is down, inside the bounds.
 */
export function nudgeApart(moved: Box, others: Record<string, Box>, bounds: Box, room: Room): Record<string, Box> {
  const out: Record<string, Box> = { ...others };
  const dist = (id: string) => Math.hypot(cx(out[id]) - cx(moved), out[id].y - moved.y);
  const order = Object.keys(out).sort((a, b) => dist(a) - dist(b));
  const queue: string[] = [""]; // "" is the moved box
  let guard = 0;
  while (queue.length && guard++ < 96) {
    const pid = queue.shift()!;
    const p = pid === "" ? moved : out[pid];
    for (const id of order) {
      if (id === pid || !hits(p, out[id])) continue;
      const all = candidates(p, out[id], pid === "", bounds, room);
      const list = all.filter((c, i) => i === all.length - 1 || within(c, bounds)); // down is always kept
      const clear = (c: Box) => !hits(c, moved) && !hits(c, p) && order.every((k) => k === id || !hits(c, out[k]));
      const next = list.find(clear) || list.find((c) => !hits(c, moved) && !hits(c, p)) || list[list.length - 1];
      out[id] = next;
      queue.push(id);
    }
  }
  return out;
}

/** A free spot for `box` next to `fixed` (right, left, below, above), inside the bounds and clear of `others`; else below it. */
export function placeBeside(fixed: Box, box: Box, others: Box[], bounds: Box, gap = 0): Box {
  const spots: Box[] = [
    { ...box, x: right(fixed) + gap, y: fixed.y },
    { ...box, x: fixed.x - gap - box.w, y: fixed.y },
    { ...box, x: fixed.x, y: bottom(fixed) + gap },
    { ...box, x: fixed.x, y: fixed.y - gap - box.h },
  ];
  const free = (b: Box) => within(b, bounds) && !hits(b, fixed) && !others.some((o) => hits(b, o));
  return spots.find(free) || spots.find((b) => within(b, bounds) && !hits(b, fixed)) || spots[2];
}

/**
 * An edge drag as a splitter: `a`'s `edge` moves by `delta` and `b`, the neighbour on that edge, gives up
 * or takes the same span. The delta is clamped so `a` keeps `minA` and `b` keeps `minB`.
 */
export function splitResize(a: Box, b: Box, edge: Edge, delta: number, minA: Size, minB: Size): { a: Box; b: Box; delta: number } {
  const horiz = edge === "e" || edge === "w";
  const aLen = horiz ? a.w : a.h, bLen = horiz ? b.w : b.h;
  const aMin = horiz ? minA.w : minA.h, bMin = horiz ? minB.w : minB.h;
  // e / s: a grows by d, b shrinks by d; w / n: a's near edge moves by d (d < 0 grows a), b grows by d
  const lo = edge === "e" || edge === "s" ? -(aLen - aMin) : -(bLen - bMin);
  const hi = edge === "e" || edge === "s" ? bLen - bMin : aLen - aMin;
  const d = Math.max(Math.min(lo, 0), Math.min(Math.max(hi, 0), delta));
  if (edge === "e") return { a: { ...a, w: a.w + d }, b: { ...b, x: b.x + d, w: b.w - d }, delta: d };
  if (edge === "s") return { a: { ...a, h: a.h + d }, b: { ...b, y: b.y + d, h: b.h - d }, delta: d };
  if (edge === "w") return { a: { ...a, x: a.x + d, w: a.w - d }, b: { ...b, w: b.w + d }, delta: d };
  return { a: { ...a, y: a.y + d, h: a.h - d }, b: { ...b, h: b.h + d }, delta: d };
}
