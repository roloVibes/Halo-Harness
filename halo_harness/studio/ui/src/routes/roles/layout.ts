// The Roles canvas geometry (3.0.7.0 R2): one labelled column box per tier
// (graph.tiers: tier 0 on the left, the implicit last tier on the right; a
// lineup without tiers is one box, "all"), the cards stacked inside their
// tier's column. A box is drawn around its cards wherever they were dragged;
// a collapsed box is its label strip and a count; an empty tier keeps its
// column slot so a card can be dropped into it. `autoLayout` places every
// card in its column; the saved positions win over it.
import type { Graph, Pos, Tier } from "./types";

export const CARD_W = 224;
export const CARD_H = 112;
export const PAD = 18;
export const HEAD = 40;
const GX = 70;
const GY = 22;
const TOP = 24;
const LEFT = 24;
const GC = 26; // between the card columns inside one tier box

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

export function autoLayout(graph: Graph): Record<string, Pos> {
  const pos: Record<string, Pos> = {};
  const xs = columns(graph);
  graph.tiers.forEach((t, col) => {
    const c = colsOf(t);
    t.node_ids.forEach((id, i) => {
      pos[id] = { x: xs[col] + PAD + (i % c) * (CARD_W + GC), y: TOP + HEAD + Math.floor(i / c) * (CARD_H + GY) };
    });
  });
  for (const n of graph.nodes) if (!pos[n.id]) pos[n.id] = { x: LEFT + PAD, y: TOP + HEAD };
  return pos;
}

/** Every card's position: the saved one, else its column slot. */
export function placeAll(graph: Graph, saved: Record<string, Pos>): Record<string, Pos> {
  const auto = autoLayout(graph);
  const out: Record<string, Pos> = {};
  for (const n of graph.nodes) out[n.id] = saved[n.id] || auto[n.id];
  return out;
}

function slot(x0: number, h = CARD_H): Box {
  return { x: x0, y: TOP, w: CARD_W + PAD * 2, h: HEAD + h + PAD };
}

/** The box of tier `t` (its column starts at `x0`): around its cards, or its label strip when collapsed, or its empty slot. */
export function tierBox(t: Tier, x0: number, pos: Record<string, Pos>, collapsed: boolean, except = ""): Box {
  const ps = t.node_ids.filter((id) => id !== except).map((id) => pos[id]).filter(Boolean);
  if (!ps.length) return collapsed ? { ...slot(x0), h: HEAD + 10 } : slot(x0, CARD_H * 0.6);
  const x = Math.min(...ps.map((p) => p.x)) - PAD;
  const y = Math.min(...ps.map((p) => p.y)) - HEAD;
  if (collapsed) return { x, y, w: CARD_W + PAD * 2, h: HEAD + 10 };
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

/** An edge between two cards: down from the source's bottom into the target's top in one column, else side to side. */
export function edgePath(a: Pos, b: Pos): { d: string; mx: number; my: number } {
  if (Math.abs(b.x - a.x) < CARD_W / 2) {
    const down = b.y >= a.y;
    const x1 = a.x + CARD_W / 2, x2 = b.x + CARD_W / 2, y1 = down ? a.y + CARD_H : a.y, y2 = down ? b.y : b.y + CARD_H;
    const dy = Math.max(30, Math.abs(y2 - y1) / 2) * (down ? 1 : -1);
    return { d: `M${x1},${y1} C${x1 + 40},${y1 + dy} ${x2 + 40},${y2 - dy} ${x2},${y2}`, mx: x1 + 30, my: (y1 + y2) / 2 };
  }
  const fwd = b.x > a.x;
  const x1 = fwd ? a.x + CARD_W : a.x, x2 = fwd ? b.x : b.x + CARD_W, y1 = a.y + CARD_H / 2, y2 = b.y + CARD_H / 2;
  const dx = Math.max(50, Math.abs(x2 - x1) / 2) * (fwd ? 1 : -1);
  return { d: `M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`, mx: (x1 + x2) / 2, my: (y1 + y2) / 2 - 6 };
}
