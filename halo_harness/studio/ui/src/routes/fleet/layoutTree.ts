// A tree laid out in layers (3.1.5.0 R3, the owner "saw a chain where there was a fan"): every node's children
// fanned out side by side under it (as many to a row as `per`, the next row under the first), the parent centred over
// its fan, an elbow edge from the parent's bottom over a bus to each child's top (a later row's edges run down the gaps
// between the first row's subtrees, never through a node). Every node has the same size, so a label is fitted to it
// and no two labels can overlap. Pure. 3.3.11.0 R2: shared by Roles Live (routes/roles/liveLayout.ts) and the Session
// Map; 3.3.16.0 R2 "the Fleet fold": the Fleet Map is gone, Agents -> Live (and Session's Map, its thumbnail) is the
// one tree that uses it.
const TREE_W = 176;
const TREE_H = 58;
const HG = 12;
const VG = 30;

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

