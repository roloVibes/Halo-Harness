// Agents (Alt+2) has four tabs (3.6.0.2 R52): `crew` 1 · Agents, `workflows` 2 · Workflows, `map` 3 · Map, `live` 4 · Live
// (what a session is doing now, drawn on the map it really follows). Every older door lands on one of them:
// `?mode=agents&view=live` on Live; `?mode=roles|orchestra|team|fleet` and `?mode=agents&view=cast|roles|team|orchestra|runs`
// on the Map, `view=flows` (3.6.0.0 R2's id for the Workflows tab) on Workflows; a replay (`&replay=<id>`, `halo replay
// open`) stays on the Map, where its scrubber is (R55). A saved section, a `focus` frame, an attention row's `o` and a
// pack's route that name an old word land the same way (lib/store.ts goSection). routes/agents/store.ts takes the view
// (onAgentsView); this file has no React and no store of its own, so lib/store.ts may import it and node runs it
// (tests/test_agents_door.py). `&run=<id>` (a goal run) opens on the Map's drawer.
export type AgentsView = "crew" | "workflows" | "map" | "live";
export const AGENTS_VIEWS: AgentsView[] = ["crew", "workflows", "map", "live"];
/** The words of the sections Agents took in, and the tab each one lands on. */
export const AGENTS_DOORS: Record<string, AgentsView> = { roles: "map", orchestra: "map", team: "map", fleet: "map" };
/** The views of the tabs before 3.6.0.0 R5 and where each lands now (`live` is a tab again: 3.6.0.2 R52). */
export const OLD_VIEWS: Record<string, AgentsView> = { cast: "map", roles: "map", team: "map", orchestra: "map", runs: "map",
  flows: "workflows" };
/** 3.5.0.0 took Fleet out; an old `?mode=fleet` link says so once, on the Map. */
export const FLEET_NOTE = "Fleet left Halo in 3.5: this machine's sessions run on the Map";

const isView = (v: string): v is AgentsView => (AGENTS_VIEWS as string[]).includes(v);

function query(search?: string): URLSearchParams | null {
  try {
    return new URLSearchParams(search ?? location.search);
  } catch {
    return null;
  }
}

/** The tab a page's URL asks Agents for, and the word it came by ('' when the URL names none of Agents' doors). */
export function urlDoor(search?: string): { view: AgentsView | ""; word: string } {
  const q = query(search);
  if (!q) return { view: "", word: "" };
  const word = q.get("mode") || "";
  const view = q.get("view") || "";
  if (word === "agents" && q.get("replay")) return { view: "map", word }; // R55: a replay stays on the Map
  if (word === "agents") return { view: isView(view) ? view : OLD_VIEWS[view] || "", word };
  return { view: AGENTS_DOORS[word] || "", word: AGENTS_DOORS[word] ? word : "" };
}

/** The goal run a page's URL names (`&run=<id>`): routes/crew/run opens it in the Map's drawer. */
export function urlRun(search?: string): string {
  return query(search)?.get("run") || "";
}

/** The section a word opens and, for one of Agents' old words, the tab it lands on. */
export function doorOf(word: string): { section: string; view: AgentsView | "" } {
  const view = AGENTS_DOORS[word];
  return view ? { section: "agents", view } : { section: word, view: "" };
}

/** A view word of any age (an old link's `cast`, `flows`) as the tab it is now ('' for none). */
export function viewOf(word: string): AgentsView | "" {
  return isView(word) ? word : OLD_VIEWS[word] || "";
}

/** Where a live panel's old door (routes/agents/fleetDoor.ts showFleetPanel) lands: the Attention panel, an agent's rows,
 *  Local -> Hosts, or Agents -> Live, where a run is watched (R52: fleet-activity, fleet-costs and the rest). */
export function panelDoor(id: string): "attention" | "agent" | "local" | "live" {
  if (id === "fleet-attention") return "attention";
  if (id === "fleet-agent") return "agent";
  return id === "fleet-ollama" || id === "ollama" ? "local" : "live";
}

/** R56 (decision 4): the tab Agents opens on, decided once before its first draw. A door's tab wins; else 4 · Live while
 *  a session he has talked to is open here (`rows`: this harness's open sessions; a turn, or a message asked, busy or
 *  between turns; a Studio-started one with no message yet, T10, does not count); else `last`, the tab used last. */
export function openingView(door: AgentsView | "", rows: { turns?: number | null; asked?: boolean | null }[], last: AgentsView): AgentsView {
  return door || (rows.some((r) => Number(r.turns) > 0 || !!r.asked) ? "live" : last);
}

/** The coordinator's ruling on R56 for a page that boots on Agents: its one quiet line while the session list is read. */
export const READING_SESSIONS = "Reading the sessions.";
/** ...and how long it waits for that list before it opens on the tab used last. */
export const OPEN_WAIT_MS = 1500;

/** The opening tab once the session list may be unread: '' (draw no view yet) until it has been read (`read`) or the
 *  wait ran out (`timedOut`: the tab used last); a door's tab at once. */
export function bootView(door: AgentsView | "", read: boolean, rows: Parameters<typeof openingView>[1], last: AgentsView,
                         timedOut: boolean): AgentsView | "" {
  if (door) return door;
  return read ? openingView("", rows, last) : timedOut ? last : "";
}

/** The tab used last as this browser stored it (`halo.studio.agents-view`; an old `flows` is Workflows; R52: Live too). */
export function lastViewOf(v: string | null): AgentsView {
  return v === "workflows" || v === "flows" ? "workflows" : v === "map" || v === "live" ? v : "crew";
}

type Door = (view: AgentsView, word: string) => void;
let take: Door | null = null;
let waiting: [AgentsView, string] | null = null;

/** routes/agents/store.ts registers the one taker; a door that came before it waits for it. */
export function onAgentsView(fn: Door): void {
  take = fn;
  if (waiting) (fn(...waiting), (waiting = null));
}

/** Agents on `view` (`word`: the door it came by; `fleet` shows its line the first time). */
export function agentsDoor(view: AgentsView, word = "agents"): void {
  if (take) take(view, word);
  else waiting = [view, word];
}
