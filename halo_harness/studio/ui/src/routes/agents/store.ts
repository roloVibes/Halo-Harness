// Agents' view (3.3.16.0 R1, lib/agentsDoor.ts): Cast, Runs or Live. Runs is a flag here; Cast and Live are the Roles
// canvas's Plan | Live (routes/roles/store.ts canvasView), so the canvas bar's own switch, the L key and this one
// never disagree. Cast and Live draw Roles' workspace (`roles`), Runs Orchestra's (`orchestra`): their layouts, status
// lines and panels keep those ids. `note` is a folded section's one line, the first time this browser comes by its old
// door: Team's (`?mode=team`), and 3.3.16.0 R2 Fleet's (`?mode=fleet`, which also turns Live's fleet scope on and, with
// `&mission=<id>`, opens that mission in Runs).
import { FLEET_NOTE, onAgentsView, TEAM_NOTE, urlDoor, urlMission, type AgentsView } from "../../lib/agentsDoor";
import { createStore, studio, useStore, writeLocal, type AgentsPart } from "../../lib/store";
import { roles, setCanvasView, useRoles } from "../roles/store";
import { setScope } from "./live/scope";
import { openMission } from "../fleet/mload";

export type AgentsState = { runs: boolean; note: string; board: boolean }; // 3.3.16.0 R3: board = the Workflows view

const NOTES: Record<string, [string, string]> = {
  team: ["halo.studio.team-note", TEAM_NOTE],
  fleet: ["halo.studio.fleet-note", FLEET_NOTE],
};

function noteOnce(word: string): string {
  const got = NOTES[word];
  if (!got) return "";
  const [key, line] = got;
  try {
    if (localStorage.getItem(key)) return "";
  } catch {
    return line; // nothing remembered in a private window: the line shows each time
  }
  writeLocal(key, "seen");
  return line;
}

const first = urlDoor();
export const agents = createStore<AgentsState>({ runs: first.view === "runs", note: noteOnce(first.word), board: first.view === "workflows" });
if (first.view === "runs" && urlMission()) window.setTimeout(() => openMission(urlMission()), 0); // `?mode=fleet&mission=<id>`

/** Agents on `view`; `word` is the door it came by (`team` and `fleet` show their line the first time; `fleet` is
 *  Live with the fleet scope on). */
export function setAgentsView(view: AgentsView, word = "agents"): void {
  const note = noteOnce(word);
  const board = view === "workflows";
  agents.update((s) => (s.runs === (view === "runs") && s.board === board && !note ? {} : { runs: view === "runs", board, ...(note ? { note } : {}) }));
  if (view !== "runs" && !board) setCanvasView(view === "live" ? "live" : "plan");
  if (word === "fleet") setScope("fleet");
}

onAgentsView(setAgentsView); // goSection("roles" | "orchestra" | "team" | "fleet"), goSection("agents", view)

export function dismissNote(): void {
  agents.update((s) => (s.note ? { note: "" } : {}));
}

export function agentsView(): AgentsView {
  return agents.get().board ? "workflows" : agents.get().runs ? "runs" : roles.get().canvasView === "live" ? "live" : "cast";
}

export function useAgentsView(): AgentsView {
  const runs = useStore(agents, (s) => s.runs);
  const board = useStore(agents, (s) => s.board);
  const live = useRoles((s) => s.canvasView === "live");
  return board ? "workflows" : runs ? "runs" : live ? "live" : "cast";
}

/** The workspace Agents draws now: roles (Cast, Live) or orchestra (Runs). */
export const agentsPart = (): AgentsPart => (agents.get().runs ? "orchestra" : "roles");
export const useAgentsPart = (): AgentsPart => useStore(agents, (s) => (s.runs ? "orchestra" : "roles"));

/** Agents is on screen and draws `part` (the keys and the glow of each workspace run only then). */
export function onPart(part: AgentsPart): boolean {
  return studio.get().section === "agents" && !agents.get().board && agentsPart() === part; // R3: the board is neither
}
