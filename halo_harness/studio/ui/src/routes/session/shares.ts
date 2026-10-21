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
