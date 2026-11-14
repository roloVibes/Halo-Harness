// Agents' view (3.3.16.0 R1, lib/agentsDoor.ts): Cast, Live or Workflows. Cast and Live are the Roles canvas's Plan |
// Live (routes/roles/store.ts canvasView), so the canvas bar's own switch, the L key and this one never disagree; both
// draw Roles' workspace (`roles`: its layout, status line and panels keep that id); Workflows is the board (a flag here).
// `note` is a folded section's one line, the first time this browser comes by its old door: Team's (`?mode=team`),
// 3.4.0.0 D Runs' (`?mode=orchestra`, `?view=runs`, R). 3.4.0.0 D "the runs fold": the Runs
// view and its workspace (`orchestra`) are gone -- a goal run is a job on Live, a finished one a row of History.
import { onAgentsView, RUNS_NOTE, TEAM_NOTE, urlDoor, urlRun, type AgentsView } from "../../lib/agentsDoor";
import { createStore, studio, useStore, writeLocal, type AgentsPart } from "../../lib/store";
import { counts, fleet } from "../fleet/store";
import { roles, setCanvasView, useRoles } from "../roles/store";
import { openRun } from "./run/door";

// 3.3.16.0 R3: board = the Workflows view; 3.6.0.0 R1: crew = the Agents tab, `chosen` = a door or the person named a view
export type AgentsState = { note: string; board: boolean; crew: boolean; chosen: boolean };
const LAST = "halo.studio.agents-view"; // 3.6.0.0 R1: the tab used last, where Agents opens when no door names one

const NOTES: Record<string, [string, string]> = {
  team: ["halo.studio.team-note", TEAM_NOTE],
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
function lastView(): AgentsView {
  try {
    const v = localStorage.getItem(LAST);
    return v === "cast" || v === "live" || v === "workflows" ? v : "crew";
  } catch {
    return "crew";
  }
}

// No door: while a session runs here Agents opens on Live (the design: "on the Map while a session runs"; Live is R1's
// running picture), else on the tab used last (the Agents tab the first time). A door or a pick of the person's wins.
const opening: AgentsView = first.view || lastView();
export const agents = createStore<AgentsState>({ note: noteOnce(first.word), board: opening === "workflows", crew: opening === "crew", chosen: !!first.view });
if (!first.view && opening !== "crew") window.setTimeout(() => setCanvasView(opening === "live" ? "live" : "plan"), 0);

/** Once, before the person is on Agents: a session runs here, so Agents will open on Live (never a flip under them). */
function liveWhileRunning(): void {
  const s = agents.get();
  if (s.chosen || counts(fleet.get()).live === 0 || (studio.get().section === "agents" && !first.view && seenHere)) return;
  agents.update(() => ({ crew: false, board: false, chosen: true }));
  if (roles.get().canvasView !== "live") setCanvasView("live");
}
let seenHere = false; // Agents was on screen with the opening view: a session starting later does not move it
studio.subscribe(() => { if (studio.get().section === "agents" && !seenHere) window.setTimeout(() => { seenHere = studio.get().section === "agents"; }, 1500); }); // the first answer of the live view has come by then
fleet.subscribe(liveWhileRunning);
window.setTimeout(liveWhileRunning, 0);
if (first.view && urlRun()) window.setTimeout(() => void openRun(urlRun()), 0); // `&run=<id>`: on Live, or its report in History

/** Agents on `view`; `word` is the door it came by (`team`, `runs` show their line the first time). */
export function setAgentsView(view: AgentsView, word = "agents"): void {
  const note = noteOnce(word);
  const board = view === "workflows";
  const crew = view === "crew";
  writeLocal(LAST, view);
  agents.update((s) => (s.board === board && s.crew === crew && s.chosen && !note ? {} : { board, crew, chosen: true, ...(note ? { note } : {}) }));
  if (!board && !crew) setCanvasView(view === "live" ? "live" : "plan");
}

onAgentsView(setAgentsView); // goSection("roles" | "orchestra" | "team"), goSection("agents", view)

export function dismissNote(): void {
  agents.update((s) => (s.note ? { note: "" } : {}));
}

export function agentsView(): AgentsView {
  return agents.get().crew ? "crew" : agents.get().board ? "workflows" : roles.get().canvasView === "live" ? "live" : "cast";
}

export function useAgentsView(): AgentsView {
  const board = useStore(agents, (s) => s.board);
  const crew = useStore(agents, (s) => s.crew);
  const live = useRoles((s) => s.canvasView === "live");
  return crew ? "crew" : board ? "workflows" : live ? "live" : "cast";
}

/** The workspace Agents draws: roles (Cast and Live; 3.4.0.0 D: the only one, Runs' went). */
export const agentsPart = (): AgentsPart => "roles";
export const useAgentsPart = (): AgentsPart => "roles";

/** Agents is on screen and draws `part` (the keys and the glow of each workspace run only then). */
export function onPart(part: AgentsPart): boolean {
  return studio.get().section === "agents" && !agents.get().board && !agents.get().crew && agentsPart() === part; // R3: the board is neither; 3.6.0.0 R1: nor the Agents tab
}
