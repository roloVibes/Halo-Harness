// Each agent's own share of the session's spend, for Session's Cost panel
// (3.1.8.0 R6). An agent row's `cost_usd` is its own session meter's running
// total, and a sub-agent's spend is rolled into its parent's meter when it
// finishes (agent/subagent.py), so a parent's figure already holds every
// finished child's: its own share is its figure minus its finished
// children's, and a finished child is counted once, on its own row. The main
// agent's figure is the session's total (the terminal's), the higher of its
// row and the session row (whichever source moved last). The shares add up to
// the session's total plus what running sub-agents have spent so far (their
// spend joins the total when they finish).
// 3.3.3.1 "cost counts what it knows": the session's `cost_usd` is the priced
// part of the spend; `cost_complete === false` with the main agent's own model
// in `cost_unknown` means main's own calls had no price, so its line says
// "no price" (`unpricedMain`) instead of a $0.0000 that reads as free.
import type { AgentRow, SessionRow } from "../fleet/types";

const FINISHED = ["done", "failed", "stopped"];
const usd = (a: AgentRow) => Number(a.cost_usd) || 0;

/** agent_id -> what that agent spent itself (never below zero). */
export function ownCosts(ss: SessionRow): Map<string, number> {
  const agents = ss.agents || [];
  const total = Number(ss.cost_usd) || 0;
  const out = new Map<string, number>();
  for (const a of agents) {
    const base = a.parent ? usd(a) : Math.max(total, usd(a));
    const kids = agents.filter((k) => k.parent === a.agent_id && FINISHED.includes(String(k.state)));
    out.set(a.agent_id, Math.max(0, Math.round((base - kids.reduce((s, k) => s + usd(k), 0)) * 1e6) / 1e6));
  }
  return out;
}

/** A model ref without its route prefix (`dbx:databricks-glm-5-3` -> `databricks-glm-5-3`). */
export const bareModel = (m: string | null | undefined) => String(m || "").replace(/^[a-z]+:/, "");

/** True when the session is incomplete and `model` is one of the refs that answered with no price. */
export function isUnpriced(ss: SessionRow, model: string | null | undefined): boolean {
  if (ss.cost_complete !== false || !model) return false;
  const want = bareModel(model);
  return (ss.cost_unknown || []).some((m) => bareModel(m) === want);
}

/** The main agent's id when its own calls had no price (and it spent nothing priced itself), else null. */
export function unpricedMain(ss: SessionRow, own: Map<string, number>): string | null {
  const main = (ss.agents || []).find((a) => !a.parent);
  if (!main || !isUnpriced(ss, main.model || ss.model)) return null;
  return (own.get(main.agent_id) || 0) > 0 ? null : main.agent_id;
}

/** "main's model databricks-glm-5-3 reports no price: ..." for the ticker's title, or "" when complete. */
export function partialTitle(ss: SessionRow): string {
  if (ss.cost_complete !== false) return "";
  const main = bareModel(((ss.agents || []).find((a) => !a.parent) || {}).model || ss.model);
  const unknown = (ss.cost_unknown || []).map(bareModel);
  const others = unknown.filter((m) => m !== main);
  const who = [unknown.includes(main) ? `main's model ${main}` : "", others.join(", ")].filter(Boolean).join(" and ") || "a model";
  return `${who} ${who.includes(" and ") || others.length > 1 ? "report" : "reports"} no price: this is what the priced agents spent`;
}
