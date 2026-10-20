// The Roles canvas geometry (3.0.7.0 R2): one labelled column box per tier
// (graph.tiers: tier 0 on the left, the implicit last tier on the right; a
// lineup without tiers is one box, "all"), the cards stacked inside their
// tier's column. A box is drawn around its cards wherever they were dragged;
// a collapsed box is its label strip and a count; an empty tier keeps its
// column slot so a card can be dropped into it. `autoLayout` places every
// card in its column; the saved positions win over it. 3.1.5.0 R3: a lineup
// with one tier lays its members out as a fan under main (main centred on
// top, the others side by side under it, FAN to a row), and an edge to a
// card below its source runs down from the source's bottom into the target's top.
// 3.1.6.0 R1: a tier with a model or a trigger has a taller head (a row for
// its model pill and trigger chip, `headOf`); edge labels: labels.ts.
import type { Graph, Pos, Tier } from "./types";

export const CARD_W = 224;
export const CARD_H = 112;
export const PAD = 18;
export const HEAD = 40;
const CHIPS = 22;

/** A tier box's head: its label strip, plus a chip row when it names a model or a trigger. */
export const headOf = (t: Tier) => HEAD + (t.model || t.trigger ? CHIPS : 0);
const GX = 70;
const GY = 22;
const TOP = 24;
const LEFT = 24;
const GC = 26; // between the card columns inside one tier box
const FAN = 4; // a one-tier lineup's members to a row under main
const FAN_GY = 56; // between main and its fan (room for the edges)

export type Box = { x: number; y: number; w: number; h: number };

/** Card columns inside a tier box: one up to four cards, then up to three. */
const colsOf = (t: Tier) => (t.node_ids.length > 4 ? Math.min(3, Math.ceil(t.node_ids.length / 4)) : 1);

/** Where each tier's column box starts (left to right, each as wide as its card columns). */
export function columns(graph: Graph): number[] {
  const xs: number[] = [];
  let x = LEFT;
  for (const t of graph.tiers) {
    xs.push(x);
    const c = colsOf(t);
    x += PAD * 2 + c * CARD_W + (c - 1) * GC + GX;
  }
  return xs;
}

/** One tier: main on top, centred over its members, who fan out in rows of FAN under it. */
function fanLayout(graph: Graph): Record<string, Pos> | null {
  const t = graph.tiers[0];
  const main = graph.nodes.find((n) => n.role === "main" && t.node_ids.includes(n.id));
  const rest = t.node_ids.filter((id) => id !== main?.id);
  if (!main || !rest.length) return null;
  const per = Math.min(FAN, rest.length);
  const rowW = per * CARD_W + (per - 1) * GC;
  const x0 = LEFT + PAD, y0 = TOP + headOf(t);
  const pos: Record<string, Pos> = { [main.id]: { x: x0 + (rowW - CARD_W) / 2, y: y0 } };
  rest.forEach((id, i) => {
    const row = Math.floor(i / per), inRow = Math.min(per, rest.length - row * per);
    const off = ((per - inRow) * (CARD_W + GC)) / 2;
    pos[id] = { x: x0 + off + (i % per) * (CARD_W + GC), y: y0 + CARD_H + FAN_GY + row * (CARD_H + GY) };
  });
  return pos;
}

export function autoLayout(graph: Graph): Record<string, Pos> {
  const fan = graph.tiers.length === 1 ? fanLayout(graph) : null;
  if (fan) {
    for (const n of graph.nodes) if (!fan[n.id]) fan[n.id] = { x: LEFT + PAD, y: TOP + HEAD };
    return fan;
  }
  const pos: Record<string, Pos> = {};
  const xs = columns(graph);
  graph.tiers.forEach((t, col) => {
    const c = colsOf(t);
    t.node_ids.forEach((id, i) => {
      pos[id] = { x: xs[col] + PAD + (i % c) * (CARD_W + GC), y: TOP + headOf(t) + Math.floor(i / c) * (CARD_H + GY) };
    });
  });
  for (const n of graph.nodes) if (!pos[n.id]) pos[n.id] = { x: LEFT + PAD, y: TOP + HEAD };
  return pos;
}

/** Every card's position: the saved one, else its column slot -- never so high or so far left that its tier box's
 *  head would leave the canvas (3.1.6.0 R1: a card dropped at the top of a box, a head that grew a chip row). */
export function placeAll(graph: Graph, saved: Record<string, Pos>): Record<string, Pos> {
  const auto = autoLayout(graph);
  const head: Record<string, number> = {};
  for (const t of graph.tiers) for (const id of t.node_ids) head[id] = headOf(t);
  const out: Record<string, Pos> = {};
  for (const n of graph.nodes) {
    const p = saved[n.id] || auto[n.id];
    out[n.id] = { x: Math.max(PAD + 2, p.x), y: Math.max((head[n.id] ?? HEAD) + 4, p.y) };
  }
  return out;
}

function slot(x0: number, head: number, h = CARD_H): Box {
  return { x: x0, y: TOP, w: CARD_W + PAD * 2, h: head + h + PAD };
}

/** The box of tier `t` (its column starts at `x0`): around its cards, or its label strip when collapsed, or its empty slot. */
export function tierBox(t: Tier, x0: number, pos: Record<string, Pos>, collapsed: boolean, except = ""): Box {
  const head = headOf(t);
  const ps = t.node_ids.filter((id) => id !== except).map((id) => pos[id]).filter(Boolean);
  if (!ps.length) return collapsed ? { ...slot(x0, head), h: head + 10 } : slot(x0, head, CARD_H * 0.6);
  const x = Math.min(...ps.map((p) => p.x)) - PAD;
  const y = Math.min(...ps.map((p) => p.y)) - head;
  if (collapsed) return { x, y, w: CARD_W + PAD * 2, h: head + 10 };
  return { x, y, w: Math.max(...ps.map((p) => p.x)) + CARD_W + PAD - x, h: Math.max(...ps.map((p) => p.y)) + CARD_H + PAD - y };
}

const inside = (b: Box, p: Pos) => p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h;

/** The tier a card dropped at world point `p` lands in (the smallest box under it), leaving the dragged card out of its own box. */
export function tierAt(graph: Graph, pos: Record<string, Pos>, collapsed: Record<string, boolean>, p: Pos, dragged: string): Tier | undefined {
  let best: Tier | undefined;
  let area = Infinity;
  const xs = columns(graph);
  graph.tiers.forEach((t, col) => {
    const b = tierBox(t, xs[col], pos, !!collapsed[t.name], dragged);
    if (inside(b, p) && b.w * b.h < area) {
      best = t;
      area = b.w * b.h;
    }
  });
  return best;
}

/** The ids of the cards inside collapsed tier boxes. */
export function hiddenCards(graph: Graph, collapsed: Record<string, boolean>): Set<string> {
  return new Set(graph.tiers.filter((t) => collapsed[t.name]).flatMap((t) => t.node_ids));
}

/** The world size the canvas scrolls over. */
export function extent(graph: Graph, pos: Record<string, Pos>): { w: number; h: number } {
  const ps = Object.values(pos);
  const xs = columns(graph);
  return {
    w: Math.max((xs[xs.length - 1] ?? LEFT) + CARD_W + PAD * 2 + 40, 600, ...ps.map((p) => p.x + CARD_W + 60)),
    h: Math.max(320, ...ps.map((p) => p.y + CARD_H + 80)),
  };
}

/** An edge's cubic curve: start, two control points, end (`edgePath` draws it; labels.ts walks it). */
export type Curve = [number, number, number, number, number, number, number, number];

/** An edge between two cards: down from the source's bottom into the target's top in one column, else side to side. */
export function edgeCurve(a: Pos, b: Pos): Curve {
  if (b.y >= a.y + CARD_H + 16 && Math.abs(b.x - a.x) >= CARD_W / 2) {
    const x1 = a.x + CARD_W / 2, y1 = a.y + CARD_H, x2 = b.x + CARD_W / 2, y2 = b.y;
    const dy = Math.max(24, (y2 - y1) / 2);
    return [x1, y1, x1, y1 + dy, x2, y2 - dy, x2, y2];
  }
  if (Math.abs(b.x - a.x) < CARD_W / 2) {
    const down = b.y >= a.y;
    const x1 = a.x + CARD_W / 2, x2 = b.x + CARD_W / 2, y1 = down ? a.y + CARD_H : a.y, y2 = down ? b.y : b.y + CARD_H;
    const dy = Math.max(30, Math.abs(y2 - y1) / 2) * (down ? 1 : -1);
    return [x1, y1, x1 + 40, y1 + dy, x2 + 40, y2 - dy, x2, y2];
  }
  const fwd = b.x > a.x;
  const x1 = fwd ? a.x + CARD_W : a.x, x2 = fwd ? b.x : b.x + CARD_W, y1 = a.y + CARD_H / 2, y2 = b.y + CARD_H / 2;
  const dx = Math.max(50, Math.abs(x2 - x1) / 2) * (fwd ? 1 : -1);
  return [x1, y1, x1 + dx, y1, x2 - dx, y2, x2, y2];
}

export function edgePath(a: Pos, b: Pos): { d: string; c: Curve } {
  const c = edgeCurve(a, b);
  return { d: `M${c[0]},${c[1]} C${c[2]},${c[3]} ${c[4]},${c[5]} ${c[6]},${c[7]}`, c };
}

/** The point at `t` (0..1) along a curve. */
export function curveAt(c: Curve, t: number): Pos {
  const u = 1 - t, a = u * u * u, b = 3 * u * u * t, d = 3 * u * t * t, e = t * t * t;
  return { x: a * c[0] + b * c[2] + d * c[4] + e * c[6], y: a * c[1] + b * c[3] + d * c[5] + e * c[7] };
}
