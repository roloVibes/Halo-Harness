// Agents' view (3.3.16.0 R1, lib/agentsDoor.ts): Cast, Live or Workflows. Cast and Live are the Roles canvas's Plan |
// Live (routes/roles/store.ts canvasView), so the canvas bar's own switch, the L key and this one never disagree; both
// draw Roles' workspace (`roles`: its layout, status line and panels keep that id); Workflows is the board (a flag here).
// `note` is a folded section's one line, the first time this browser comes by its old door: Team's (`?mode=team`),
// 3.3.16.0 R2 Fleet's (`?mode=fleet`, which also turns Live's fleet scope on and, with `&mission=<id>`, opens that
// mission's panel on Live), 3.4.0.0 D Runs' (`?mode=orchestra`, `?view=runs`, R). 3.4.0.0 D "the runs fold": the Runs
// view and its workspace (`orchestra`) are gone -- a goal run is a job on Live, a finished one a row of History.
import { FLEET_NOTE, onAgentsView, RUNS_NOTE, TEAM_NOTE, urlDoor, urlMission, urlRun, type AgentsView } from "../../lib/agentsDoor";
import { createStore, studio, useStore, writeLocal, type AgentsPart } from "../../lib/store";
import { roles, setCanvasView, useRoles } from "../roles/store";
import { setScope } from "./live/scope";
import { openMissionPanel } from "./fleetDoor";
import { openRun } from "./run/door";

export type AgentsState = { note: string; board: boolean }; // 3.3.16.0 R3: board = the Workflows view

const NOTES: Record<string, [string, string]> = {
  team: ["halo.studio.team-note", TEAM_NOTE],
  fleet: ["halo.studio.fleet-note", FLEET_NOTE],
  runs: ["halo.studio.runs-note", RUNS_NOTE],
  orchestra: ["halo.studio.runs-note", RUNS_NOTE],
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
export const agents = createStore<AgentsState>({ note: noteOnce(first.word), board: first.view === "workflows" });
if (first.view && urlMission()) window.setTimeout(() => openMissionPanel(urlMission()), 0); // `?mode=fleet&mission=<id>`: its panel on Live
if (first.view && urlRun()) window.setTimeout(() => void openRun(urlRun()), 0); // `&run=<id>`: on Live, or its report in History

/** Agents on `view`; `word` is the door it came by (`team`, `fleet`, `runs` show their line the first time; `fleet` is
 *  Live with the fleet scope on). */
export function setAgentsView(view: AgentsView, word = "agents"): void {
  const note = noteOnce(word);
  const board = view === "workflows";
  agents.update((s) => (s.board === board && !note ? {} : { board, ...(note ? { note } : {}) }));
  if (!board) setCanvasView(view === "live" ? "live" : "plan");
  if (word === "fleet") setScope("fleet");
}

onAgentsView(setAgentsView); // goSection("roles" | "orchestra" | "team" | "fleet"), goSection("agents", view)

export function dismissNote(): void {
  agents.update((s) => (s.note ? { note: "" } : {}));
}

export function agentsView(): AgentsView {
  return agents.get().board ? "workflows" : roles.get().canvasView === "live" ? "live" : "cast";
}

export function useAgentsView(): AgentsView {
  const board = useStore(agents, (s) => s.board);
  const live = useRoles((s) => s.canvasView === "live");
  return board ? "workflows" : live ? "live" : "cast";
}

/** The workspace Agents draws: roles (Cast and Live; 3.4.0.0 D: the only one, Runs' went). */
export const agentsPart = (): AgentsPart => "roles";
export const useAgentsPart = (): AgentsPart => "roles";

/** Agents is on screen and draws `part` (the keys and the glow of each workspace run only then). */
export function onPart(part: AgentsPart): boolean {
  return studio.get().section === "agents" && !agents.get().board && agentsPart() === part; // R3: the board is neither
}
