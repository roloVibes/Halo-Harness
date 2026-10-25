// What a card drop does on the Roles canvas (Halo 3.2.2.0 R5; the owner:
// "When I move the parts ... over another block ... they disappear"). The
// dropped card keeps its spot; every card it overlaps steps aside within its
// own tier (lib/geometry.ts `nudgeApart`, the tier box as the bounds, which
// regrow downward through `tierBox`): sideways first, then it takes the
// dropped card's old spot (in the dropped card's own tier), then down. A drop
// into another tier lands beside the card it was dropped on, never on it
// (`placeBeside`). The live drag shows the same room being made (Canvas.tsx's
// `pos` memo calls `dropPatch` on every move). Pure functions.
import { hits, nudgeApart, placeBeside, union, type Box } from "../../lib/geometry";
import { CARD_H, CARD_W, PAD, columns, headOf, tierBox } from "./layout";
import type { Graph, Pos, Tier } from "./types";

const GAP = 16;

export const cardBox = (p: Pos): Box => ({ x: p.x, y: p.y, w: CARD_W, h: CARD_H });

/** The area a tier's cards may take: inside its box, under its head; downward it grows without end. */
function inner(t: Tier, b: Box): Box {
  return { x: b.x + PAD, y: b.y + headOf(t), w: Math.max(CARD_W, b.w - PAD * 2), h: 1e6 };
}

/** The cards that overlap the box most first. */
function hitList(b: Box, ids: string[], pos: Record<string, Pos>): string[] {
  const area = (id: string) => {
    const c = cardBox(pos[id]);
    return Math.max(0, Math.min(b.x + b.w, c.x + c.w) - Math.max(b.x, c.x)) * Math.max(0, Math.min(b.y + b.h, c.y + c.h) - Math.max(b.y, c.y));
  };
  return ids.filter((id) => pos[id] && hits(b, cardBox(pos[id]))).sort((p, q) => area(q) - area(p));
}

/**
 * The positions that change when card `id` lands at `at` (its spot before: `pos[id]`): the dropped card's
 * own (beside the card it was dropped on when it joins `into`, another tier) and every card that steps aside.
 * Cards in collapsed tiers are hidden and stay where they are.
 */
export function dropPatch(graph: Graph, pos: Record<string, Pos>, collapsed: Record<string, boolean>, id: string, at: Pos, into?: Tier): Record<string, Pos> {
  const xs = columns(graph);
  const home = graph.tiers.find((t) => t.node_ids.includes(id));
  const target = into || home;
  const boxOf = (t: Tier) => tierBox(t, xs[graph.tiers.indexOf(t)], pos, !!collapsed[t.name], id);
  let land = { x: at.x, y: at.y };
  if (into && into !== home) {
    const mates = into.node_ids.filter((k) => k !== id && pos[k]);
    const onto = hitList(cardBox(land), mates, pos)[0];
    if (onto) {
      const rest = mates.filter((k) => k !== onto).map((k) => cardBox(pos[k]));
      const b = placeBeside(cardBox(pos[onto]), cardBox(land), rest, union(inner(into, boxOf(into)), cardBox(land)), GAP);
      land = { x: b.x, y: b.y };
    }
  }
  const patch: Record<string, Pos> = { [id]: land };
  const moved = cardBox(land);
  for (const t of graph.tiers) {
    if (collapsed[t.name]) continue;
    const ids = t.node_ids.filter((k) => k !== id && pos[k]);
    if (!hitList(moved, ids, pos).length) continue;
    const own = t === target;
    const bounds = own ? union(inner(t, boxOf(t)), moved) : inner(t, boxOf(t));
    const others = Object.fromEntries(ids.map((k) => [k, cardBox(pos[k])]));
    const from = own && t === home && pos[id] ? cardBox(pos[id]) : undefined;
    const after = nudgeApart(moved, others, bounds, { minW: CARD_W, minH: CARD_H, gap: GAP, from });
    for (const k of ids) if (after[k].x !== others[k].x || after[k].y !== others[k].y) patch[k] = { x: Math.round(after[k].x), y: Math.round(after[k].y) };
  }
  return patch;
}
