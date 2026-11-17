// The palette's Agents lines (3.6.0.2 R52): "Agents: 1 · Agents", "Agents: 2 · Workflows", "Agents: 3 · Map",
// "Agents: 4 · Live", each with its key; a goal run's lines follow in the same group (routes/crew/run/commands.ts).
import type { AgentsView } from "../../lib/agentsDoor";
import { goSection } from "../../lib/store";
import { WORDS } from "../crew/map/truth";

export type AgentsCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

const VIEWS: [AgentsView, string, string, string][] = [
  ["crew", "1 · Agents", "1", "make an agent: its name, what it does, its model, what it may use; try it, save it"],
  ["workflows", "2 · Workflows", "2", "your agents in steps, in order; try it, save it"],
  ["map", "3 · Map", "3", "who main hands work to, and when; History replays on it"], // R55: Map is the plan
  ["live", `4 · ${WORDS.live}`, "4", "what a session is doing now, drawn on the map it really follows"],
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
