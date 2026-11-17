// Agents' tab (lib/agentsDoor.ts, 3.6.0.2 R52): 1 · Agents (`crew`), 2 · Workflows (`workflows`), 3 · Map (`map`) or
// 4 · Live (`live`). No door (R56, decision 4): while a session he has talked to is open here Agents opens on Live, else on
// the tab used last (1 · Agents the first time); decided once, the first time Agents is about to draw, and never again in
// this page: a session starting, getting busy or ending never moves the tab. A door or a pick of the person's wins. `note`
// is an old door's one line, the first time this browser comes by it (`?mode=fleet`: Fleet left Halo in 3.5).
import { FLEET_NOTE, OPEN_WAIT_MS, bootView, lastViewOf, onAgentsView, urlDoor, urlRun, type AgentsView } from "../../lib/agentsDoor";
import { createStore, studio, useStore, writeLocal } from "../../lib/store";
import { fleet, localId } from "../fleet/store";
import { openRows } from "../crew/map/litStore";
import { openRun } from "../crew/run/door";

export type AgentsState = { note: string; view: AgentsView; chosen: boolean; waiting: boolean };
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
    return lastViewOf(localStorage.getItem(LAST));
  } catch {
    return "crew";
  }
}

export const agents = createStore<AgentsState>({ note: noteOnce(first.word), view: first.view || lastView(), chosen: !!first.view, waiting: false });

/** R56: once, as Agents is about to draw for the first time (a door named the tab: nothing to decide). The session list
 *  not read yet (a page that boots on Agents): `waiting` -- the tab bar and one quiet line, no view -- until it has been
 *  read, or OPEN_WAIT_MS ran out (then the tab used last), or he picks a tab (the coordinator's ruling). */
let decided = !!first.view;
let started = false;
let unFleet = () => {};
let timer = 0;
function settle(timedOut: boolean): boolean {
  if (decided) return true;
  const s = agents.get(), st = fleet.get();
  const view = s.chosen ? s.view : bootView("", st.loaded, openRows(st, localId(st)), s.view, timedOut);
  if (!view) return false;
  decided = true;
  unFleet();
  window.clearTimeout(timer);
  if (view !== s.view) agents.update(() => ({ view, chosen: true, waiting: false }));
  else if (s.waiting) agents.update(() => ({ waiting: false }));
  return true;
}
function decideOnce(): void {
  if (decided || started || studio.get().section !== "agents") return;
  started = true;
  stop();
  if (settle(false)) return;
  agents.update(() => ({ waiting: true }));
  unFleet = fleet.subscribe(() => void settle(false));
  timer = window.setTimeout(() => void settle(true), OPEN_WAIT_MS);
}
const stop = decided ? () => {} : studio.subscribe(decideOnce);
decideOnce(); // a page that boots on Agents decides before its first draw
if (urlRun()) window.setTimeout(() => void openRun(urlRun()), 0); // `&run=<id>`: the goal run in the Map's drawer

/** Agents on `view`; `word` is the door it came by (`fleet` shows its line the first time). */
export function setAgentsView(view: AgentsView, word = "agents"): void {
  const note = noteOnce(word);
  writeLocal(LAST, view);
  agents.update((s) => (s.view === view && s.chosen && !s.waiting && !note ? {} : { view, chosen: true, waiting: false, ...(note ? { note } : {}) }));
  settle(false); // a tab he picks while the session list is read is his: decided
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

/** 3.6.0.2 R1 R3: another machine's session picked in 4 · Live (`sid`, "" for none) and the local pick it was made over
 *  (`at`). It holds until he picks another: in Live's picker, or in Session (a different local pick there voids it; its
 *  [Open in Agents -> Live] clears it, routes/session/store.ts `openInLive`). */
export const livePickAway = createStore<{ sid: string; at: string }>({ sid: "", at: "" });
