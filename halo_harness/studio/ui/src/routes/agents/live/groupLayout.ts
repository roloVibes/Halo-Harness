// Live in groups, laid out (3.3.16.3): the layered tree of routes/fleet/layoutTree.ts (a parent over its fan, an elbow
// edge to each child over a bus) where a task's or a square's agents (groups.ts) are ONE child of the parent -- a box
// with a title bar, its agents in a grid inside it (up to `gper` to a row: four at the spread density), and the parent's
// edge goes to the box's top, not to each agent. Inside the box an agent's own children hang under it as the tree does;
// a square's box can sit inside a task's box (one level). A collapsed box is its title bar alone. Pure.
import type { Dims } from "../../fleet/layoutTree";
import type { LiveNode } from "../../roles/liveModel";
import type { GroupTag } from "./groups";

export const G_PAD = 12;
export const G_GAP = 16; // between two rows of a box's grid
const HEAD = 54; // the title bar: the task, then the counts line
const HEAD_WHY = 72; // with the second line (Auto's pick, a square's DOES)

type Item = { kind: "node" | "group"; id: string; kids: Item[]; rows: Item[][]; w: number; h: number; head: number; open: boolean };
export type GroupBox = { g: GroupTag; x: number; y: number; w: number; h: number; head: number; open: boolean; depth: number;
  from: string | null; d: string; members: LiveNode[]; by: string };
export type Placed = { id: string; x: number; y: number; depth: number; from: string | null; d: string };

export const isBoxed = (n: LiveNode): boolean => !!n.group && n.group.kind !== "tier";

export function headOf(g: GroupTag): number {
  return g.why ? HEAD_WHY : HEAD;
}

export function groupForest(nodes: LiveNode[], dims: Dims & { per: number }, gper: number, closed: Set<string>) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const meta = new Map<string, GroupTag>();
  const members = new Map<string, LiveNode[]>();
  const kids = new Map<string, LiveNode[]>();
  const roots: LiveNode[] = [];
  for (const n of nodes) {
    if (isBoxed(n)) meta.set(n.group!.id, n.group!);
    if (n.parent && byId.has(n.parent) && n.parent !== n.id) kids.set(n.parent, [...(kids.get(n.parent) || []), n]);
    else roots.push(n);
  }
  const box = (id: string) => { const n = byId.get(id); return n && isBoxed(n) ? n.group!.id : ""; };
  const chain = (g: string) => { const out: string[] = []; for (let x: string | undefined = g; x && !out.includes(x); x = meta.get(x)?.outer) out.push(x); return out; };
  for (const n of nodes) for (const g of chain(box(n.id))) members.set(g, [...(members.get(g) || []), n]);
  /** The box right under `inside` that holds node `id` ("" when it is not in one). */
  const under = (id: string, inside: string) => { const c = chain(box(id)); const i = inside ? c.indexOf(inside) : c.length; return i > 0 ? c[i - 1] : ""; };
  const node = (id: string, depth = 0): Item => {
    const own = box(id), seen = new Set<string>(), out: Item[] = [];
    if (depth < 24) for (const c of kids.get(id) || []) {
      const g = box(c.id) === own ? "" : under(c.id, own);
      if (!g) out.push(node(c.id, depth + 1));
      else if (!seen.has(g)) (seen.add(g), out.push(group(g, depth + 1)));
    }
    return { kind: "node", id, kids: out, rows: [], w: 0, h: 0, head: 0, open: true };
  };
  const group = (gid: string, depth: number): Item => {
    const g = meta.get(gid)!, open = !closed.has(gid), seen = new Set<string>(), out: Item[] = [];
    const firsts = g.parent && byId.has(g.parent) ? kids.get(g.parent) || [] : roots;
    if (open) for (const c of firsts) {
      if (box(c.id) === gid) out.push(node(c.id, depth + 1));
      else { const h = under(c.id, gid); if (h && !seen.has(h)) (seen.add(h), out.push(group(h, depth + 1))); }
    }
    return { kind: "group", id: gid, kids: out, rows: [], w: 0, h: 0, head: headOf(g), open };
  };
  const top: Item[] = [], seenTop = new Set<string>();
  for (const r of roots) {
    const g = box(r.id) ? chain(box(r.id)).pop()! : "";
    if (!g) top.push(node(r.id));
    else if (!seenTop.has(g) && !(meta.get(g)!.parent && byId.has(meta.get(g)!.parent!))) (seenTop.add(g), top.push(group(g, 0)));
  }
  const measure = (t: Item): void => {
    t.kids.forEach(measure);
    const per = t.kind === "group" ? gper : dims.per;
    const budget = per * dims.w + (per - 1) * dims.hg; // a row of boxes wraps at the width of `per` agents, so wide groups stack
    t.rows = [];
    for (const k of t.kids) {
      const row = t.rows[t.rows.length - 1];
      const w = row ? row.reduce((s, x) => s + x.w + dims.hg, 0) + k.w : Infinity;
      if (!row || row.length >= per || w > budget) t.rows.push([k]);
      else row.push(k);
    }
    const rowW = t.rows.map((r) => r.reduce((s, k) => s + k.w, 0) + dims.hg * (r.length - 1));
    if (t.kind === "node") {
      t.w = Math.max(dims.w, ...rowW);
      t.h = dims.h + t.rows.reduce((s, r) => s + dims.vg + Math.max(...r.map((k) => k.h)), 0);
    } else {
      t.w = Math.max(dims.w + 2 * G_PAD, 300, ...rowW.map((w) => w + 2 * G_PAD));
      t.h = t.head + (t.open && t.rows.length ? G_PAD + t.rows.reduce((s, r) => s + Math.max(...r.map((k) => k.h)), 0) + G_GAP * (t.rows.length - 1) + G_PAD : 0);
    }
  };
  top.forEach(measure);
  return { top, meta, members, byId };
}

function elbow(x1: number, y1: number, x2: number, y2: number, vg: number, via?: { gx: number; bus0: number }): string {
  const bus = y2 - vg / 2;
  return via ? `M${x1} ${y1} V${via.bus0} H${via.gx} V${bus} H${x2} V${y2}` : `M${x1} ${y1} V${bus} H${x2} V${y2}`;
}

/** Place item `t` with its top-left at x, y: the node boxes into `out`, the group boxes into `groups`. */
export function placeItem(t: Item, x: number, y: number, dims: Dims, f: ReturnType<typeof groupForest>, out: Placed[], groups: GroupBox[],
                          depth = 0, from: string | null = null, d = ""): void {
  if (t.kind === "group") {
    const g = f.meta.get(t.id)!;
    groups.push({ g, x, y, w: t.w, h: t.h, head: t.head, open: t.open, depth, from, d, members: f.members.get(t.id) || [],
                  by: (g.parent && f.byId.get(g.parent)?.name) || "" });
    let cy = y + t.head + G_PAD;
    for (const row of t.rows) {
      const rw = row.reduce((s, k) => s + k.w, 0) + dims.hg * (row.length - 1);
      let cx = x + (t.w - rw) / 2;
      for (const k of row) (placeItem(k, cx, cy, dims, f, out, groups, depth + 1), (cx += k.w + dims.hg));
      cy += Math.max(...row.map((k) => k.h)) + G_GAP;
    }
    return;
  }
  const nx = x + (t.w - dims.w) / 2;
  out.push({ id: t.id, x: nx, y, depth, from, d });
  const px = nx + dims.w / 2, py = y + dims.h;
  let cy = y + dims.h + dims.vg, gaps: number[] = [];
  const bus0 = cy - dims.vg / 2;
  t.rows.forEach((row, ri) => {
    const rw = row.reduce((s, k) => s + k.w, 0) + dims.hg * (row.length - 1);
    let cx = x + (t.w - rw) / 2;
    const xs: number[] = [];
    for (const k of row) {
      const kx = cx + k.w / 2;
      const gx = ri ? gaps.reduce((b, g) => (Math.abs(g - kx) < Math.abs(b - kx) ? g : b), gaps[0]) : 0;
      placeItem(k, cx, cy, dims, f, out, groups, depth + 1, t.id, elbow(px, py, kx, cy, dims.vg, ri ? { gx, bus0 } : undefined));
      xs.push(cx);
      cx += k.w + dims.hg;
    }
    if (!ri) gaps = [xs[0] - dims.hg / 2, ...row.map((k, i) => xs[i] + k.w + dims.hg / 2)];
    cy += Math.max(...row.map((k) => k.h)) + dims.vg;
  });
}

/** The whole forest with groups: its roots side by side from `left` (a machine box's `gap` between two roots). */
export function placeGrouped(nodes: LiveNode[], dims: Dims & { per: number }, gper: number, closed: Set<string>, left: number, top: number, gap: number) {
  const f = groupForest(nodes, dims, gper, closed);
  const placed: Placed[] = [], groups: GroupBox[] = [];
  let x = left;
  for (const r of f.top) {
    placeItem(r, x, top, dims, f, placed, groups);
    x += r.w + dims.hg + gap;
  }
  const w = f.top.reduce((s, r) => s + r.w, 0) + (dims.hg + gap) * Math.max(0, f.top.length - 1);
  return { placed, groups, w, h: Math.max(0, ...f.top.map((r) => r.h)) };
}
