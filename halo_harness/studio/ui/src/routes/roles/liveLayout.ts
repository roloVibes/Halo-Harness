// Roles Live laid out (3.3.11.0 R2): the Session Map's own layered layout (routes/fleet/layoutTree.ts
// `forestOf` + `placeForest`: parents above their children, siblings side by side in spawn order, an elbow
// edge from each parent over a bus to its children) with bigger nodes and two densities -- spread (room for
// the pick's reason on each node) and compact (more of a big tree on one screen). Each lineup card that some
// nodes match is a faint group: the box around its nodes, its name over it. Pure: LiveMap.tsx draws it.
import { forestOf, placeForest, type Dims, type Placed } from "../fleet/layoutTree";
import type { LiveNode } from "./liveModel";

export type Density = "compact" | "spread";
export const DENSITY: Record<Density, Dims & { per: number }> = {
  spread: { w: 228, h: 92, hg: 22, vg: 44, per: 6 },
  compact: { w: 180, h: 70, hg: 10, vg: 28, per: 9 },
};
const MARGIN = 28;
const HEAD = 22; // room over the top row for a group's name
const GROUP_PAD = 9;

export type LiveBox = { node: LiveNode; x: number; y: number; w: number; h: number; depth: number; from: string | null; d: string };
export type LiveGroup = { card: string; label: string; x: number; y: number; w: number; h: number; count: number };
export type LiveGeometry = { width: number; height: number; boxes: LiveBox[]; groups: LiveGroup[] };

export function liveLayout(nodes: LiveNode[], density: Density = "spread"): LiveGeometry {
  const dims = DENSITY[density] || DENSITY.spread;
  const forest = forestOf(nodes.map((n) => ({ id: n.id, parent: n.parent })), dims.per, dims);
  const placed: Placed[] = [];
  placeForest(forest, MARGIN, MARGIN + HEAD, dims, placed);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const boxes: LiveBox[] = placed.map((p) => ({ node: byId.get(p.id)!, x: p.x, y: p.y, w: dims.w, h: dims.h, depth: p.depth, from: p.from, d: p.d }));
  const groups = new Map<string, LiveGroup>();
  for (const b of boxes) {
    if (!b.node.card) continue;
    const g = groups.get(b.node.card);
    const x0 = b.x - GROUP_PAD, y0 = b.y - GROUP_PAD, x1 = b.x + b.w + GROUP_PAD, y1 = b.y + b.h + GROUP_PAD;
    if (!g) groups.set(b.node.card, { card: b.node.card, label: b.node.cardLabel, x: x0, y: y0, w: x1 - x0, h: y1 - y0, count: 1 });
    else {
      const gx1 = Math.max(g.x + g.w, x1), gy1 = Math.max(g.y + g.h, y1);
      g.x = Math.min(g.x, x0);
      g.y = Math.min(g.y, y0);
      g.w = gx1 - g.x;
      g.h = gy1 - g.y;
      g.count += 1;
    }
  }
  return { width: Math.max(320, forest.w + 2 * MARGIN), height: Math.max(200, forest.h + 2 * MARGIN + HEAD), boxes, groups: [...groups.values()] };
}
