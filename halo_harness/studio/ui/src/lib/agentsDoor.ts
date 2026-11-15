// Agents (Alt+2) has three tabs (3.6.0.0 R5): `crew` 1 · Agents, `workflows` 2 · Workflows, `map` 3 · Map. Every older
// door lands on one of them: `?mode=roles|orchestra|team|fleet` and `?mode=agents&view=cast|live|roles|team|orchestra|
// runs` on the Map (where a session is lit while it runs and History replays it), `view=flows` (3.6.0.0 R2's id for the
// Workflows tab) on Workflows. A saved section, a `focus` frame, an attention row's `o` and a pack's route that name an
// old word land the same way (lib/store.ts goSection). routes/agents/store.ts takes the view (onAgentsView); this file has
// no React and no store of its own, so lib/store.ts may import it. `&run=<id>` (a goal run) opens on the Map's drawer.
export type AgentsView = "crew" | "workflows" | "map";
export const AGENTS_VIEWS: AgentsView[] = ["crew", "workflows", "map"];
/** The words of the sections Agents took in, and the tab each one lands on. */
export const AGENTS_DOORS: Record<string, AgentsView> = { roles: "map", orchestra: "map", team: "map", fleet: "map" };
/** The views of the tabs before 3.6.0.0 R5 and where each lands now. */
export const OLD_VIEWS: Record<string, AgentsView> = { cast: "map", live: "map", roles: "map", team: "map", orchestra: "map",
  runs: "map", flows: "workflows" };
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
