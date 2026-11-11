// Roles Live laid out (3.3.11.0 R2): the Session Map's own layered layout (routes/fleet/layoutTree.ts
// `forestOf` + `placeForest`: parents above their children, siblings side by side in spawn order, an elbow
// edge from each parent over a bus to its children) with bigger nodes and two densities -- spread (room for
// the pick's reason on each node) and compact (more of a big tree on one screen). Each lineup card that some
// nodes match is a faint group: the box around its nodes, its name over it. Pure: LiveMap.tsx draws it.
// 3.3.16.0 R2 (the fleet scope): each harness's nodes (its machine node, sessions, agents, mission parts) are a
// machine box the same way (`machines`), the box a dragged mission part is dropped into.
import { forestOf, placeForest, type Dims, type Placed } from "../fleet/layoutTree";
import type { LiveNode } from "./liveModel";
import { isBoxed, placeGrouped, type GroupBox } from "../agents/live/groupLayout";

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
/** `tasks`: 3.3.16.3's group boxes (a task's, a square's agents), drawn by routes/agents/live/GroupBox.tsx. */
export type LiveGeometry = { width: number; height: number; boxes: LiveBox[]; groups: LiveGroup[]; machines: LiveGroup[]; tasks: GroupBox[] };
const OPEN = new Set<string>();

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

export function liveLayout(nodes: LiveNode[], density: Density = "spread", closed: Set<string> = OPEN, rowH = 0): LiveGeometry {
  const base = DENSITY[density] || DENSITY.spread;
  const dims = rowH ? { ...base, h: base.h + rowH } : base; // 3.3.18.0: Agents' Live nodes carry the "waits on" row
  const fleet = nodes.some((n) => n.harness);
  const gap = fleet ? 2 * MACHINE_PAD : 0; // room between two machine boxes (each root is a machine, or a session in Session's map)
  const top = MARGIN + HEAD + (fleet ? MACHINE_PAD : 0);
  const left = MARGIN + (fleet ? MACHINE_PAD : 0);
  // 3.3.16.3: a task's or a square's agents are one box under their parent (routes/agents/live/groupLayout.ts)
  const laid = nodes.some(isBoxed) ? placeGrouped(nodes, dims, density === "compact" ? 5 : 4, closed, left, top, gap) : placePlain(nodes, dims, left, top, gap);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const boxes: LiveBox[] = laid.placed.map((p) => ({ node: byId.get(p.id)!, x: p.x, y: p.y, w: dims.w, h: dims.h, depth: p.depth, from: p.from, d: p.d }));
  const tasks = laid.groups;
  const groups = groupsOf(boxes.filter((b) => !isBoxed(b.node)), (b) => b.node.group?.id || b.node.card, (b) => b.node.group?.title || b.node.cardLabel, GROUP_PAD);
  const rects = [...boxes, ...tasks.map((t) => ({ ...boxes[0], node: t.members[0], x: t.x, y: t.y, w: t.w, h: t.h }))];
  const machines = fleet ? groupsOf(rects, (b) => b.node?.harness || "", (b) => (b.node?.kind === "machine" ? b.node.name : ""), MACHINE_PAD) : [];
  const extra = fleet ? 2 * MACHINE_PAD : 0;
  return { width: Math.max(320, laid.w + 2 * MARGIN + extra), height: Math.max(200, laid.h + 2 * MARGIN + HEAD + extra), boxes, groups, machines, tasks };
}

function placePlain(nodes: LiveNode[], dims: Dims & { per: number }, left: number, top: number, gap: number) {
  const forest = forestOf(nodes.map((n) => ({ id: n.id, parent: n.parent })), dims.per, dims);
  const placed: Placed[] = [];
  let x = left;
  for (const r of forest.roots) {
    placeForest({ roots: [r], w: r.w, h: r.h }, x, top, dims, placed);
    x += r.w + dims.hg + gap;
  }
  return { placed, groups: [] as GroupBox[], w: forest.w + gap * Math.max(0, forest.roots.length - 1), h: forest.h };
}
