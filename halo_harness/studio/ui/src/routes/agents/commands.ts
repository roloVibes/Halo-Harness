// The palette's Agents lines (3.3.16.0 R1): "Agents: Cast", "Agents: Live", "Agents: Workflows", each with its key; Cast's
// Roles lines and a goal run's lines follow in the same group (routes/roles/commands.ts, routes/agents/run/commands.ts:
// 3.4.0.0 D, Run a goal, stop the run, review its plan, a lane, a finished run's report).
import type { AgentsView } from "../../lib/agentsDoor";
import { goSection } from "../../lib/store";

export type AgentsCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

const VIEWS: [AgentsView, string, string, string][] = [
  ["cast", "Cast", "C", "the lineup and its bios: cards in their tiers"],
  ["live", "Live", "L", "what runs now: the session's agents and a goal run's lanes as a tree; History holds what ran"],
  ["workflows", "Workflows", "W", "the squares main may hand work to: the board, the library"],
];

export function agentsCommands(): AgentsCommand[] {
  return VIEWS.map(([view, label, kbd, hint]) => ({
    id: "agents-" + view,
    group: "Agents",
    label: `Agents: ${label}`,
    hint,
    kbd,
    run: () => goSection("agents", view),
  }));
}
