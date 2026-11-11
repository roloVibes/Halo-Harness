// Live's layout, once per STRUCTURE (3.3.18.0 "The living canvas": a long session has thousands of events and may have a
// hundred agents; the canvas must not lay out again on every frame). The layout (roles/liveLayout.ts) runs when the
// tree's shape changes -- which nodes, their parents, their boxes, the density, the folded groups -- and between two
// such changes every box is handed its fresh node (its state, its cost, what it does), so a frame repaints and never
// moves anything.
import { useMemo } from "react";
import { liveLayout, type Density, type LiveGeometry } from "../../roles/liveLayout";
import type { LiveNode } from "../../roles/liveModel";

/** The shape of a tree: the nodes, their parents and their boxes, in order. */
export function shapeOf(nodes: LiveNode[]): string {
  return nodes.map((n) => `${n.id}>${n.parent || ""}#${n.group?.id || ""}:${n.group?.outer || ""}`).join("|");
}

/** `geo` with each box's node (and each group's members) replaced by the node of the same id in `nodes`. */
export function freshen(geo: LiveGeometry, nodes: LiveNode[]): LiveGeometry {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const fresh = (n: LiveNode) => byId.get(n.id) || n;
  return {
    ...geo, boxes: geo.boxes.map((b) => ({ ...b, node: fresh(b.node) })),
    tasks: geo.tasks.map((t) => {
      const members = t.members.map(fresh);
      return { ...t, members, g: members.find((m) => m.group?.id === t.g.id)?.group || t.g };
    }),
  };
}

export function useLiveGeo(nodes: LiveNode[], density: Density, closed: string[], rowH = 0): LiveGeometry {
  const shape = shapeOf(nodes);
  const shut = closed.join("|");
  // eslint-disable-next-line react-hooks/exhaustive-deps -- laid out on the shape, not on every new node object
  const geo = useMemo(() => liveLayout(nodes, density, new Set(closed), rowH), [shape, density, shut, rowH]);
  return useMemo(() => freshen(geo, nodes), [geo, nodes]);
}
