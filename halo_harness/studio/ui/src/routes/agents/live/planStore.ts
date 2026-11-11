// The plan under Live (3.3.18.0 "The living canvas" part 2): the lineup the drawn session runs under -- its graph (the
// cards, their tiers, main's delegation lines with their words) and its enabled squares with their when -- read once per
// lineup (GET lineup/<name>, GET workflows?lineup=<name>) and kept here, apart from Cast's open lineup and the Workflows
// board, so drawing the plan on Live never moves what Cast or Workflows has open. `on` is the bar's toggle: null until
// the owner touches it or a `?plan=on|off` door names it (until then the default: on when the lineup has blocks or tiers).
import { api } from "../../../lib/api";
import { createStore, useStore } from "../../../lib/store";
import type { Graph, LineupPayload } from "../../roles/types";
import type { Board, Square } from "../workflows/store";

export type Plan = { lineup: string; graph: Graph | null; squares: Square[]; loaded: boolean; error: string };
type State = { plans: Record<string, Plan>; on: boolean | null };

/** `?plan=on|off` sets the toggle from the URL (a door, the drivers); otherwise the default rules. */
function urlPlan(): boolean | null {
  try {
    const v = new URLSearchParams(location.search).get("plan");
    return v === "on" ? true : v === "off" ? false : null;
  } catch {
    return null;
  }
}

export const planStore = createStore<State>({ plans: {}, on: urlPlan() });
export const usePlanOn = (): boolean | null => useStore(planStore, (s) => s.on);
export const setPlanOn = (on: boolean): void => planStore.update(() => ({ on }));

const asking = new Set<string>();

async function load(lineup: string): Promise<void> {
  if (asking.has(lineup)) return;
  asking.add(lineup);
  const put = (p: Partial<Plan>) => planStore.update((s) => ({ plans: { ...s.plans, [lineup]: { ...(s.plans[lineup] || blank(lineup)), ...p } } }));
  try {
    const [l, b] = await Promise.all([
      api.get<LineupPayload>("lineup/" + encodeURIComponent(lineup)),
      api.get<Board>("workflows", { lineup }).catch(() => null),
    ]);
    const squares = (b?.enabled || []).map((ref) => b?.squares.find((q) => q.ref === ref)).filter((q): q is Square => !!q && q.square);
    put({ graph: l.graph || null, squares, loaded: true, error: "" });
  } catch (e) {
    put({ loaded: true, error: (e as Error).message || "could not read the lineup" });
  } finally {
    asking.delete(lineup);
  }
}

const blank = (lineup: string): Plan => ({ lineup, graph: null, squares: [], loaded: false, error: "" });

/** The plan of `lineup` (read on first ask); null for no lineup. */
export function usePlan(lineup: string): Plan | null {
  const p = useStore(planStore, (s) => (lineup ? s.plans[lineup] || null : null));
  if (lineup && !p && !asking.has(lineup)) window.setTimeout(() => void load(lineup), 0);
  return p;
}

/** A plan worth drawing under the agents: explicit tiers, or squares main may hand work to. */
export function hasBlocks(p: Plan | null): boolean {
  return !!p?.graph && (p.squares.length > 0 || p.graph.tiers.some((t) => !t.implicit && !t.node_ids.every((id) => p.graph!.nodes.find((n) => n.id === id)?.role === "main")));
}
