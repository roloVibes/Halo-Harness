// Agents' view (3.3.16.0 R1, lib/agentsDoor.ts): Cast, Runs or Live. Runs is a flag here; Cast and Live are the Roles
// canvas's Plan | Live (routes/roles/store.ts canvasView), so the canvas bar's own switch, the L key and this one
// never disagree. Cast and Live draw Roles' workspace (`roles`), Runs Orchestra's (`orchestra`): their layouts, status
// lines and panels keep those ids. `note` is Team's one line, the first time this browser comes by `?mode=team`.
import { onAgentsView, TEAM_NOTE, urlDoor, type AgentsView } from "../../lib/agentsDoor";
import { createStore, studio, useStore, writeLocal, type AgentsPart } from "../../lib/store";
import { roles, setCanvasView, useRoles } from "../roles/store";

export type AgentsState = { runs: boolean; note: string };

const NOTE_KEY = "halo.studio.team-note";

function noteOnce(word: string): string {
  if (word !== "team") return "";
  try {
    if (localStorage.getItem(NOTE_KEY)) return "";
  } catch {
    return TEAM_NOTE; // nothing remembered in a private window: the line shows each time
  }
  writeLocal(NOTE_KEY, "seen");
  return TEAM_NOTE;
}

const first = urlDoor();
export const agents = createStore<AgentsState>({ runs: first.view === "runs", note: noteOnce(first.word) });

/** Agents on `view`; `word` is the door it came by (`team` shows Team's line the first time). */
export function setAgentsView(view: AgentsView, word = "agents"): void {
  const note = noteOnce(word);
  agents.update((s) => (s.runs === (view === "runs") && !note ? {} : { runs: view === "runs", ...(note ? { note } : {}) }));
  if (view !== "runs") setCanvasView(view === "live" ? "live" : "plan");
}

onAgentsView(setAgentsView); // goSection("roles" | "orchestra" | "team"), goSection("agents", view)

export function dismissNote(): void {
  agents.update((s) => (s.note ? { note: "" } : {}));
}

export function agentsView(): AgentsView {
  return agents.get().runs ? "runs" : roles.get().canvasView === "live" ? "live" : "cast";
}

export function useAgentsView(): AgentsView {
  const runs = useStore(agents, (s) => s.runs);
  const live = useRoles((s) => s.canvasView === "live");
  return runs ? "runs" : live ? "live" : "cast";
}

/** The workspace Agents draws now: roles (Cast, Live) or orchestra (Runs). */
export const agentsPart = (): AgentsPart => (agents.get().runs ? "orchestra" : "roles");
export const useAgentsPart = (): AgentsPart => useStore(agents, (s) => (s.runs ? "orchestra" : "roles"));

/** Agents is on screen and draws `part` (the keys and the glow of each workspace run only then). */
export function onPart(part: AgentsPart): boolean {
  return studio.get().section === "agents" && agentsPart() === part;
}
