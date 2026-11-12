// Live's "Plan under it" (3.3.18.0 "The living canvas" part 2): the lineup the drawn session runs under as blocks, the
// live agents inside the block each belongs to (planModel.ts), laid out once per structure (planLayout.ts) and handed
// fresh nodes between (liveGeo.ts's rule). On by default when that lineup has tiers or squares; the bar's toggle wins
// once touched. Only on this halo's scope. 3.4.1.0 R1: over a session's replay too (the lineup in use), and over a saved
// file with the blocks it holds (a goal run's or a mission's replay has none: its own block is its run). Part 4 (levels.ts): at the far level the blocks are
// drawn alone -- the plan's, or with the plan off the tree's own groups -- and `farOf` lays that out for Fit.
import { useMemo } from "react";
import type { WorkRecord } from "../../../lib/work/record";
import type { Density } from "../../roles/liveLayout";
import type { LiveNode } from "../../roles/liveModel";
import { useRoles } from "../../roles/store";
import { useLiveReplay } from "./replay";
import { NEAR_H, type Level } from "./levels";
import { shapeOf } from "./liveGeo";
import { groupBlocks, placeAgents, planBlocks, type Placement, type PlanBlockDef } from "./planModel";
import { planLayout, type PlanGeometry } from "./planLayout";
import { hasBlocks, usePlan, usePlanOn } from "./planStore";
import { WAITS_H } from "./WaitsRow";

export type LivePlan = { lineup: string; available: boolean; on: boolean; geo: PlanGeometry | null; farOf: () => PlanGeometry | null; midOf: () => PlanGeometry | null };

/** The lineup the session runs under: its main agent's, else the one new sessions use. */
export function lineupOf(rec: WorkRecord | null, inUse: string): string {
  const main = rec?.agents.find((a) => !a.parent);
  return (main?.lineup || inUse || "").trim();
}

export function useLivePlan(mode: string, nodes: LiveNode[], rec: WorkRecord | null, density: Density, replay: boolean, level: Level = "mid"): LivePlan {
  const inUse = useRoles((s) => s.info?.active_team || s.info?.lineup_in_use || "");
  const rep = useLiveReplay();
  const tl = rep && !rep.tl.coarse ? rep.tl : null;
  const was = useMemo(() => (tl ? ({ agents: tl.base.map((n) => ({ id: n.id, parent: n.parent, ...tl.rows.find((x) => x.id === n.id) })) } as unknown as WorkRecord) : null), [tl]);
  const here = mode === "here" && (!replay || !!was);
  if (replay) rec = was;
  const lineup = here ? rep?.plan?.lineup || lineupOf(rec, inUse) : "";
  const fetched = usePlan(rep?.plan ? "" : lineup);
  const plan = rep?.plan ? { ...rep.plan, loaded: true, error: "" } : fetched;
  const chosen = usePlanOn();
  const agents = nodes.some((n) => !n.virtual && !n.kind);
  const available = !!plan?.graph && agents;
  const on = available && (chosen ?? hasBlocks(plan));
  const blocksOf = (): { defs: PlanBlockDef[]; place: Placement } | null => {
    if (on && plan) { const defs = planBlocks(plan); return { defs, place: placeAgents(nodes, rec, plan, defs) }; }
    return here && agents ? groupBlocks(nodes) : null;
  };
  const far = level === "far" && here && agents;
  const made = useMemo(() => (on || far ? blocksOf() : null), [on, far, plan, nodes, rec]); // eslint-disable-line react-hooks/exhaustive-deps
  const rowH = WAITS_H + (level === "near" ? NEAR_H : 0);
  const key = made ? `${shapeOf(nodes)}~${[...made.place.block].map(([k, v]) => k + "=" + v).join(",")}~${made.defs.map((d) => d.id + d.when).join(",")}~${density}~${rowH}~${far}` : "";
  // eslint-disable-next-line react-hooks/exhaustive-deps -- laid out on the structure, painted on the state
  const laid = useMemo(() => (made ? planLayout(nodes, made.defs, made.place, density, rowH, far) : null), [key]);
  const geo = useMemo(() => {
    if (!laid || !made) return null;
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const fresh = (n: LiveNode) => byId.get(n.id) || n;
    const why = made.place.why;
    return { ...laid, boxes: laid.boxes.map((b) => ({ ...b, node: fresh(b.node) })),
             blocks: laid.blocks.map((b) => ({ ...b, members: (b.members.length ? b.members : nodes.filter((n) => made.place.block.get(n.id) === b.def.id)).map(fresh),
               def: b.def.kind === "none" ? { ...b.def, purpose: [...new Set(b.members.map((m) => why.get(m.id) || ""))].filter(Boolean).join("; ") || b.def.purpose } : b.def })) };
  }, [laid, nodes, made]);
  const farOf = () => { const m = blocksOf(); return m ? planLayout(nodes, m.defs, m.place, density, 0, true) : null; };
  const midOf = () => { const m = on ? blocksOf() : null; return m ? planLayout(nodes, m.defs, m.place, density, WAITS_H, false) : null; };
  return { lineup, available, on, geo, farOf, midOf };
}
