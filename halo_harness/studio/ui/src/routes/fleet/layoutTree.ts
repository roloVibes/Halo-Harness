// The map laid out as a tree (3.1.5.0 R3, Session's scope: one harness box;
// the owner "saw a chain where there was a fan"): each session's card across
// the box, its agents under it top-down, every agent's children fanned out
// side by side under it (as many to a row as the map's width holds at full
// size, `perRow`, the next row under the first), the parent centred over its fan, an elbow edge from the parent's
// bottom over a bus to each child's top (a later row's edges run down the
// gaps between the first row's subtrees, never through a node). Every node has the same width, so a label is
// fitted to it and no two labels can overlap. Pure: Map.tsx draws it.
// 3.3.11.0 R2: the layered layout itself (`forestOf` + `placeForest`, any node size) is shared with Roles Live
// (routes/roles/liveLayout.ts), and the Map reads each session's agents through the work record adapter
// (lib/work/record.ts `recordOf`), the same tree Roles Live draws.
import { recordOf } from "../../lib/work/record";
import { keyOf } from "./store";
import type { Box, Card, Geometry, NodeBox } from "./layout";
import type { Harness } from "./types";

export const TREE_W = 176;
export const TREE_H = 58;
const HG = 12;
const VG = 30;
const PAD = 14;
const HEAD = 44;
const CARD_H = 52;
const S_GAP = 20;
const MARGIN = 6;
const MIN_BOX = 340;

/** A node's size and the gaps: between siblings (`hg`) and between a parent and its fan (`vg`). */
export type Dims = { w: number; h: number; hg: number; vg: number };
export const MAP_DIMS: Dims = { w: TREE_W, h: TREE_H, hg: HG, vg: VG };
/** What the layout needs of a node: its id and the id it hangs under (none, or not in the list: a root). */
export type TreeItem = { id: string; parent?: string | null };
type T = { id: string; kids: T[]; w: number; h: number; rows: T[][] };
export type Forest = { roots: T[]; w: number; h: number };
/** A placed node: its top-left, its depth, the node it hangs under and the elbow edge into it ("" for a root without a source). */
export type Placed = { id: string; x: number; y: number; depth: number; from: string | null; d: string };

function build(items: TreeItem[]): T[] {
  const ids = new Set(items.map((r) => r.id));
  const by = new Map<string, T>(items.map((a) => [a.id, { id: a.id, kids: [], w: 0, h: 0, rows: [] }]));
  const roots: T[] = [];
  for (const r of items) {
    const t = by.get(r.id)!;
    const p = r.parent && ids.has(r.parent) && r.parent !== r.id ? by.get(r.parent) : undefined;
    (p ? p.kids : roots).push(t);
  }
  return roots;
}

/** Each subtree's width and height (a cycle in the parents is cut at depth 8). */
function measure(t: T, per: number, dims: Dims, depth = 0): void {
  if (depth > 8) t.kids = [];
  t.kids.forEach((k) => measure(k, per, dims, depth + 1));
  t.rows = [];
  for (let i = 0; i < t.kids.length; i += per) t.rows.push(t.kids.slice(i, i + per));
  const rowW = t.rows.map((r) => r.reduce((s, k) => s + k.w, 0) + dims.hg * (r.length - 1));
  t.w = Math.max(dims.w, ...rowW);
  t.h = dims.h + t.rows.reduce((s, r) => s + dims.vg + Math.max(...r.map((k) => k.h)), 0);
}

/** The roots of `items` with every subtree measured; `w` / `h` the whole forest side by side. */
export function forestOf(items: TreeItem[], per: number, dims: Dims = MAP_DIMS): Forest {
  const roots = build(items);
  roots.forEach((r) => measure(r, per, dims));
  return { roots, w: roots.reduce((n, r) => n + r.w, 0) + dims.hg * Math.max(0, roots.length - 1), h: Math.max(0, ...roots.map((r) => r.h)) };
}

/** An elbow down from the parent's bottom to a bus over the row, across, and down into the child. */
function elbow(x1: number, y1: number, x2: number, y2: number, vg: number, via?: { gx: number; bus0: number }): string {
  const bus = y2 - vg / 2;
  if (!via) return `M${x1} ${y1} V${bus} H${x2} V${y2}`;
  return `M${x1} ${y1} V${via.bus0} H${via.gx} V${bus} H${x2} V${y2}`;
}

function place(t: T, x: number, y: number, dims: Dims, out: Placed[], from: string | null, d: string, depth: number): void {
  const nx = x + (t.w - dims.w) / 2;
  out.push({ id: t.id, x: nx, y, depth, from, d });
  const px = nx + dims.w / 2, py = y + dims.h;
  let cy = y + dims.h + dims.vg;
  let gaps: number[] = [];
  const bus0 = cy - dims.vg / 2;
  t.rows.forEach((row, ri) => {
    const rw = row.reduce((s2, k) => s2 + k.w, 0) + dims.hg * (row.length - 1);
    let cx = x + (t.w - rw) / 2;
    const xs: number[] = [];
    for (const k of row) {
      const kx = cx + (k.w - dims.w) / 2 + dims.w / 2;
      // a later row's edge runs down a gap between the first row's subtrees, the one nearest its child
      const gx = ri ? gaps.reduce((b, g) => (Math.abs(g - kx) < Math.abs(b - kx) ? g : b), gaps[0]) : 0;
      place(k, cx, cy, dims, out, t.id, elbow(px, py, kx, cy, dims.vg, ri ? { gx, bus0 } : undefined), depth + 1);
      xs.push(cx);
      cx += k.w + dims.hg;
    }
    if (!ri) gaps = [xs[0] - dims.hg / 2, ...row.map((k, i) => xs[i] + k.w + dims.hg / 2)];
    cy += Math.max(...row.map((k) => k.h)) + dims.vg;
  });
}

/** Place the forest with its top-left at `x, y`; each root's edge comes from `source` (a card's bottom) when given. */
export function placeForest(f: Forest, x: number, y: number, dims: Dims, out: Placed[], source?: { x: number; y: number }): void {
  let cx = x;
  for (const r of f.roots) {
    place(r, cx, y, dims, out, null, source ? elbow(source.x, source.y, cx + r.w / 2, y, dims.vg) : "", 0);
    cx += r.w + dims.hg;
  }
}

/** How many nodes fit side by side in `width` px of map (2 to 5; 3 when the width is not known yet). */
export function perRowFor(width: number): number {
  if (!width) return 3;
  return Math.max(2, Math.min(5, Math.floor((width - 2 * (MARGIN + PAD) + HG) / (TREE_W + HG))));
}

/** One harness box (Session's scope): its sessions stacked, each card over its agents' tree. */
export function treeLayout(h: Harness, label: string, sub: string, hc: string, local: boolean, per = 3, cardH = CARD_H): Geometry {
  const geo: Geometry = { width: 0, height: 0, boxes: [], cards: [], nodes: [], edges: [], parts: [] };
  const forests = (h.sessions || []).map((s) => {
    const rec = recordOf(h, s);
    return { s, rec, f: forestOf(rec.agents.map((a) => ({ id: a.id, parent: a.parent })), per) };
  });
  const inner = Math.max(MIN_BOX - 2 * PAD, ...forests.map((x) => x.f.w));
  const ox = MARGIN + PAD;
  let y = MARGIN + HEAD;
  for (const { s, rec, f } of forests) {
    const card: Card = { x: ox, y, w: inner, h: cardH, harness: h, session: s, hc };
    geo.cards.push(card);
    y += cardH + VG * 0.6;
    const placed: Placed[] = [];
    placeForest(f, ox + (inner - f.w) / 2, y, MAP_DIMS, placed, { x: card.x + card.w / 2, y: card.y + cardH });
    const byId = new Map(rec.agents.map((a) => [a.id, a]));
    for (const p of placed) {
      const key = keyOf(h.id, s.session_id, p.id);
      const n: NodeBox = { x: p.x, y: p.y, w: TREE_W, h: TREE_H, ref: { key, h, s, a: byId.get(p.id)!.row, depth: p.depth }, hc, tree: true };
      geo.nodes.push(n);
      geo.edges.push({ from: p.from ? keyOf(h.id, s.session_id, p.from) : null, to: key, d: p.d });
    }
    y += f.h + S_GAP;
  }
  if (!forests.length) y += 34;
  const box: Box = { x: MARGIN, y: MARGIN, w: inner + 2 * PAD, h: y - MARGIN + PAD - (forests.length ? S_GAP : 0), key: "h:" + h.id, label, sub, online: true, local, hc, empty: !forests.length, lane: 0 };
  geo.boxes.push(box);
  geo.width = box.w + 2 * MARGIN;
  geo.height = Math.max(120, box.h + 2 * MARGIN);
  return geo;
}
