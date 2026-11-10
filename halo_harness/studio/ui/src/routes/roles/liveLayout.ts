// Roles Live laid out (3.3.11.0 R2): the Session Map's own layered layout (routes/fleet/layoutTree.ts
// `forestOf` + `placeForest`: parents above their children, siblings side by side in spawn order, an elbow
// edge from each parent over a bus to its children) with bigger nodes and two densities -- spread (room for
// the pick's reason on each node) and compact (more of a big tree on one screen). Each lineup card that some
// nodes match is a faint group: the box around its nodes, its name over it. Pure: LiveMap.tsx draws it.
// 3.3.16.0 R2 (the fleet scope): each harness's nodes (its machine node, sessions, agents, mission parts) are a
// machine box the same way (`machines`), the box a dragged mission part is dropped into.
import { forestOf, placeForest, type Dims, type Placed } from "../fleet/layoutTree";
import type { LiveNode } from "./liveModel";

export type Density = "compact" | "spread";
export const DENSITY: Record<Density, Dims & { per: number }> = {
  // 3.3.16.0 (the owner, Session's Map on Kali: "information gets stomped on ... it's ok if the boxes elongate to fit
  // the words, just don't squish them"): a node is wide and tall enough for its name, its role, its model beside its
  // cost and two lines of what it does; styles/nodes.css lays the lines out so none runs into another
  spread: { w: 268, h: 124, hg: 22, vg: 44, per: 6 },
  compact: { w: 240, h: 110, hg: 12, vg: 28, per: 9 },
};
const MARGIN = 28;
const HEAD = 22; // room over the top row for a group's name
const GROUP_PAD = 9;
const MACHINE_PAD = 16;

export type LiveBox = { node: LiveNode; x: number; y: number; w: number; h: number; depth: number; from: string | null; d: string };
export type LiveGroup = { card: string; label: string; x: number; y: number; w: number; h: number; count: number };
export type LiveGeometry = { width: number; height: number; boxes: LiveBox[]; groups: LiveGroup[]; machines: LiveGroup[] };

/** The box around every box `keyOf` puts in one group (`pad` px out from them). */
function groupsOf(boxes: LiveBox[], keyOf: (b: LiveBox) => string, labelOf: (b: LiveBox) => string, pad: number): LiveGroup[] {
  const groups = new Map<string, LiveGroup>();
  for (const b of boxes) {
    const k = keyOf(b);
    if (!k) continue;
    const g = groups.get(k);
    const x0 = b.x - pad, y0 = b.y - pad, x1 = b.x + b.w + pad, y1 = b.y + b.h + pad;
    if (!g) groups.set(k, { card: k, label: labelOf(b), x: x0, y: y0, w: x1 - x0, h: y1 - y0, count: 1 });
    else {
      const gx1 = Math.max(g.x + g.w, x1), gy1 = Math.max(g.y + g.h, y1);
      g.x = Math.min(g.x, x0);
      g.y = Math.min(g.y, y0);
      g.w = gx1 - g.x;
      g.h = gy1 - g.y;
      g.count += 1;
      if (!g.label) g.label = labelOf(b);
    }
  }
  return [...groups.values()];
}

export function liveLayout(nodes: LiveNode[], density: Density = "spread"): LiveGeometry {
  const dims = DENSITY[density] || DENSITY.spread;
  const fleet = nodes.some((n) => n.harness);
  const gap = fleet ? 2 * MACHINE_PAD : 0; // room between two machine boxes (each root is a machine, or a session in Session's map)
  const forest = forestOf(nodes.map((n) => ({ id: n.id, parent: n.parent })), dims.per, dims);
  const placed: Placed[] = [];
  const top = MARGIN + HEAD + (fleet ? MACHINE_PAD : 0);
  let x = MARGIN + (fleet ? MACHINE_PAD : 0);
  for (const r of forest.roots) {
    placeForest({ roots: [r], w: r.w, h: r.h }, x, top, dims, placed);
    x += r.w + dims.hg + gap;
  }
  forest.w += gap * Math.max(0, forest.roots.length - 1);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const boxes: LiveBox[] = placed.map((p) => ({ node: byId.get(p.id)!, x: p.x, y: p.y, w: dims.w, h: dims.h, depth: p.depth, from: p.from, d: p.d }));
  const groups = groupsOf(boxes, (b) => b.node.card, (b) => b.node.cardLabel, GROUP_PAD);
  const machines = fleet ? groupsOf(boxes, (b) => b.node.harness || "", (b) => (b.node.kind === "machine" ? b.node.name : ""), MACHINE_PAD) : [];
  const extra = fleet ? 2 * MACHINE_PAD : 0;
  return { width: Math.max(320, forest.w + 2 * MARGIN + extra), height: Math.max(200, forest.h + 2 * MARGIN + HEAD + extra), boxes, groups, machines };
}
