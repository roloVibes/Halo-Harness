// The palette's Agents lines (3.3.16.0 R1): "Agents: Cast", "Agents: Runs", "Agents: Live", each with its key; Cast's
// Roles lines and Runs' Orchestra lines follow in the same group (routes/roles/commands.ts, routes/orchestra/commands.ts).
import type { AgentsView } from "../../lib/agentsDoor";
import { goSection } from "../../lib/store";

export type AgentsCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

const VIEWS: [AgentsView, string, string, string][] = [
  ["cast", "Cast", "C", "the lineup and its bios: cards in their tiers"],
  ["runs", "Runs", "R", "a goal for the lineup: the plan, the lanes, the report; Test this lineup"],
  ["live", "Live", "L", "what runs now: the session's agents as a tree"],
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
