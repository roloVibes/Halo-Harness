// The map laid out as a tree (3.1.5.0 R3, Session's scope: one harness box;
// the owner "saw a chain where there was a fan"): each session's card across
// the box, its agents under it top-down, every agent's children fanned out
// side by side under it (as many to a row as the map's width holds at full
// size, `perRow`, the next row under the first), the parent centred over its fan, an elbow edge from the parent's
// bottom over a bus to each child's top (a later row's edges run down the
// gaps between the first row's subtrees, never through a node). Every node has the same width, so a label is
// fitted to it and no two labels can overlap. Pure: Map.tsx draws it.
import { keyOf } from "./store";
import type { Box, Card, Geometry, NodeBox } from "./layout";
import type { AgentRow, Harness } from "./types";

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

type T = { a: AgentRow; kids: T[]; w: number; h: number; rows: T[][] };

function build(rows: AgentRow[]): T[] {
  const ids = new Set(rows.map((r) => r.agent_id));
  const by = new Map<string, T>(rows.map((a) => [a.agent_id, { a, kids: [], w: 0, h: 0, rows: [] }]));
  const roots: T[] = [];
  for (const r of rows) {
    const t = by.get(r.agent_id)!;
    const p = r.parent && ids.has(r.parent) && r.parent !== r.agent_id ? by.get(r.parent) : undefined;
    (p ? p.kids : roots).push(t);
  }
  return roots;
}

/** Each subtree's width and height (a cycle in the parents is cut at depth 8). */
function measure(t: T, per: number, depth = 0): void {
  if (depth > 8) t.kids = [];
  t.kids.forEach((k) => measure(k, per, depth + 1));
  t.rows = [];
  for (let i = 0; i < t.kids.length; i += per) t.rows.push(t.kids.slice(i, i + per));
  const rowW = t.rows.map((r) => r.reduce((s, k) => s + k.w, 0) + HG * (r.length - 1));
  t.w = Math.max(TREE_W, ...rowW);
  t.h = TREE_H + t.rows.reduce((s, r) => s + VG + Math.max(...r.map((k) => k.h)), 0);
}

/** An elbow down from the parent's bottom to a bus over the row, across, and down into the child. */
function elbow(x1: number, y1: number, x2: number, y2: number, via?: { gx: number; bus0: number }): string {
  const bus = y2 - VG / 2;
  if (!via) return `M${x1} ${y1} V${bus} H${x2} V${y2}`;
  return `M${x1} ${y1} V${via.bus0} H${via.gx} V${bus} H${x2} V${y2}`;
}

function place(t: T, x: number, y: number, h: Harness, sid: string, hc: string, geo: Geometry, parent: NodeBox | null, d: string, depth: number): void {
  const key = keyOf(h.id, sid, t.a.agent_id);
  const s = h.sessions.find((x2) => x2.session_id === sid)!;
  const n: NodeBox = { x: x + (t.w - TREE_W) / 2, y, w: TREE_W, h: TREE_H, ref: { key, h, s, a: t.a, depth }, hc, tree: true };
  geo.nodes.push(n);
  geo.edges.push({ from: parent ? parent.ref.key : null, to: key, d });
  const px = n.x + TREE_W / 2, py = n.y + TREE_H;
  let cy = y + TREE_H + VG;
  let gaps: number[] = [];
  const bus0 = cy - VG / 2;
  t.rows.forEach((row, ri) => {
    const rw = row.reduce((s2, k) => s2 + k.w, 0) + HG * (row.length - 1);
    let cx = x + (t.w - rw) / 2;
    const xs: number[] = [];
    for (const k of row) {
      const kx = cx + (k.w - TREE_W) / 2 + TREE_W / 2;
      // a later row's edge runs down a gap between the first row's subtrees, the one nearest its child
      const gx = ri ? gaps.reduce((b, g) => (Math.abs(g - kx) < Math.abs(b - kx) ? g : b), gaps[0]) : 0;
      place(k, cx, cy, h, sid, hc, geo, n, elbow(px, py, kx, cy, ri ? { gx, bus0 } : undefined), depth + 1);
      xs.push(cx);
      cx += k.w + HG;
    }
    if (!ri) gaps = [xs[0] - HG / 2, ...row.map((k, i) => xs[i] + k.w + HG / 2)];
    cy += Math.max(...row.map((k) => k.h)) + VG;
  });
}

/** One harness box (Session's scope): its sessions stacked, each card over its agents' tree. */
/** How many nodes fit side by side in `width` px of map (2 to 5; 3 when the width is not known yet). */
export function perRowFor(width: number): number {
  if (!width) return 3;
  return Math.max(2, Math.min(5, Math.floor((width - 2 * (MARGIN + PAD) + HG) / (TREE_W + HG))));
}

export function treeLayout(h: Harness, label: string, sub: string, hc: string, local: boolean, per = 3, cardH = CARD_H): Geometry {
  const geo: Geometry = { width: 0, height: 0, boxes: [], cards: [], nodes: [], edges: [], parts: [] };
  const forests = (h.sessions || []).map((s) => {
    const roots = build(s.agents || []);
    roots.forEach((r) => measure(r, per));
    return { s, roots, w: roots.reduce((n, r) => n + r.w, 0) + HG * Math.max(0, roots.length - 1), h: Math.max(0, ...roots.map((r) => r.h)) };
  });
  const inner = Math.max(MIN_BOX - 2 * PAD, ...forests.map((f) => f.w));
  const ox = MARGIN + PAD;
  let y = MARGIN + HEAD;
  for (const f of forests) {
    const card: Card = { x: ox, y, w: inner, h: cardH, harness: h, session: f.s, hc };
    geo.cards.push(card);
    y += cardH + VG * 0.6;
    let x = ox + (inner - f.w) / 2;
    for (const r of f.roots) {
      place(r, x, y, h, f.s.session_id, hc, geo, null, elbow(card.x + card.w / 2, card.y + cardH, x + r.w / 2, y), 0);
      x += r.w + HG;
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
