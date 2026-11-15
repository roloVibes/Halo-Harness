// Agents' tab (lib/agentsDoor.ts, 3.6.0.0 R5): 1 · Agents (`crew`), 2 · Workflows (`workflows`) or 3 · Map (`map`).
// No door: while a session runs here Agents opens on the Map (the design: "on the Map while a session runs"), else on
// the tab used last (1 · Agents the first time). A door or a pick of the person's wins. `note` is an old door's one
// line, the first time this browser comes by it (`?mode=fleet`: Fleet left Halo in 3.5).
import { FLEET_NOTE, onAgentsView, urlDoor, urlRun, type AgentsView } from "../../lib/agentsDoor";
import { createStore, studio, useStore, writeLocal } from "../../lib/store";
import { counts, fleet } from "../fleet/store";
import { openRun } from "../crew/run/door";

export type AgentsState = { note: string; view: AgentsView; chosen: boolean };
const LAST = "halo.studio.agents-view"; // the tab used last, where Agents opens when no door names one

const NOTES: Record<string, [string, string]> = { fleet: ["halo.studio.fleet-note", FLEET_NOTE] };

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
    return v === "workflows" || v === "flows" ? "workflows" : v === "map" ? "map" : "crew";
  } catch {
    return "crew";
  }
}

export const agents = createStore<AgentsState>({ note: noteOnce(first.word), view: first.view || lastView(), chosen: !!first.view });

/** Once, before the person is on Agents: a session runs here, so Agents will open on the Map (never a flip under them). */
function mapWhileRunning(): void {
  const s = agents.get();
  if (s.chosen || counts(fleet.get()).live === 0 || (studio.get().section === "agents" && !first.view && seenHere)) return;
  agents.update(() => ({ view: "map", chosen: true }));
}
let seenHere = false; // Agents was on screen with the opening tab: a session starting later does not move it
studio.subscribe(() => { if (studio.get().section === "agents" && !seenHere) window.setTimeout(() => { seenHere = studio.get().section === "agents"; }, 1500); });
fleet.subscribe(mapWhileRunning);
window.setTimeout(mapWhileRunning, 0);
if (urlRun()) window.setTimeout(() => void openRun(urlRun()), 0); // `&run=<id>`: the goal run in the Map's drawer

/** Agents on `view`; `word` is the door it came by (`fleet` shows its line the first time). */
export function setAgentsView(view: AgentsView, word = "agents"): void {
  const note = noteOnce(word);
  writeLocal(LAST, view);
  agents.update((s) => (s.view === view && s.chosen && !note ? {} : { view, chosen: true, ...(note ? { note } : {}) }));
}

onAgentsView(setAgentsView); // goSection("roles" | "orchestra" | "team" | "fleet"), goSection("agents", view)

export function dismissNote(): void {
  agents.update((s) => (s.note ? { note: "" } : {}));
}

export function agentsView(): AgentsView {
  return agents.get().view;
}

export function useAgentsView(): AgentsView {
  return useStore(agents, (s) => s.view);
}
