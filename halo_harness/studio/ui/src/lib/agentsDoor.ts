// 3.3.16.0 R1 "Agents: one section": Team, Roles and Orchestra fold into Agents (Alt+2). The old words stay doors:
// `?mode=roles` lands on Cast (`&view=live` on Live); `?mode=agents&view=cast|live|workflows` is the door itself. A saved
// section, a `focus` frame, an attention row's `o` and a pack's route that name an old word land the same way
// (lib/store.ts goSection). routes/agents/store.ts takes the view (onAgentsView); this file has no React and no store
// of its own, so lib/store.ts may import it. 3.3.16.0 R2 "the Fleet fold": `fleet` is a door too -- Agents on Live with
// the fleet scope on (`?scope=fleet`), the Mission panel up when it names a mission (`?mode=fleet&mission=<id>`); its
// line once. 3.3.16.0 R3: `workflows` -- the board of squares. 3.3.18.0 "The living canvas": a bare `?mode=agents` lands
// on Live. 3.4.0.0 D "the runs fold": Runs and its Start screen are gone -- a goal run is a job on Live while it runs
// and a row of History once it ended. Every door that named Runs (`?mode=orchestra`, `?mode=team`,
// `?mode=agents&view=runs`, the R key) lands on Live; one that names a run (`&run=<id>`) opens that run where it is
// (routes/agents/run/door.ts: its lead on Live while it runs, its report in History once it ended).
export type AgentsView = "cast" | "live" | "workflows";
export type LiveScope = "here" | "fleet";
export const AGENTS_VIEWS: AgentsView[] = ["cast", "live", "workflows"];
/** The words of the sections Agents took in, and the view each one lands on (3.4.0.0 D: Runs' words on Live). */
export const AGENTS_DOORS: Record<string, AgentsView> = { roles: "cast", orchestra: "live", team: "live", fleet: "live" };
export const TEAM_NOTE = "Team's board is gone; a run on Live shows who owns what";
export const FLEET_NOTE = "Fleet is Agents -> Live now: machines in Setup -> Machines, models in Local";
/** 3.4.0.0 D: Runs' line, once in this browser, when an old door that named it brings you here. */
export const RUNS_NOTE = "Runs is gone: a goal runs on Live (Run a goal on its bar); a finished run is in History";

const isView = (v: string): v is AgentsView => (AGENTS_VIEWS as string[]).includes(v);

function query(search?: string): URLSearchParams | null {
  try {
    return new URLSearchParams(search ?? location.search);
  } catch {
    return null;
  }
}

/** The view a page's URL asks Agents for, and the word it came by ('' when the URL names none of Agents' doors). An old
 *  view word (`runs`) or section word (`orchestra`, `team`) comes as the word `runs`: Live, with Runs' line once. */
export function urlDoor(search?: string): { view: AgentsView | ""; word: string } {
  const q = query(search);
  if (!q) return { view: "", word: "" };
  const word = q.get("mode") || "";
  const view = q.get("view") || "";
  if (word === "agents") return view === "runs" ? { view: "live", word: "runs" } : { view: isView(view) ? view : "live", word }; // 3.3.18.0: what is live
  if (word === "roles") return { view: view === "live" ? "live" : "cast", word };
  if (word === "orchestra") return { view: "live", word: "runs" };
  return { view: AGENTS_DOORS[word] || "", word: AGENTS_DOORS[word] ? word : "" };
}

/** 3.4.0.0 D: the run a page's URL names (`&run=<id>`): routes/agents/run/door.ts opens it on Live or in History. */
export function urlRun(search?: string): string {
  return query(search)?.get("run") || "";
}

/** The scope a page's URL asks Live for: `?scope=fleet|here`, or the fleet for `?mode=fleet` ('' = Live decides). */
export function urlScope(search?: string): LiveScope | "" {
  const q = query(search);
  const s = q?.get("scope") || "";
  if (s === "fleet" || s === "here") return s;
  return q?.get("mode") === "fleet" ? "fleet" : "";
}

/** The mission a page's URL names (`?mode=fleet&mission=<id>`), else '' (3.4.0.0 D: its panel opens on Live). */
export function urlMission(search?: string): string {
  return query(search)?.get("mission") || "";
}

/** The section a word opens and, for one of Agents' old words, the view it lands on. */
export function doorOf(word: string): { section: string; view: AgentsView | "" } {
  const view = AGENTS_DOORS[word];
  return view ? { section: "agents", view } : { section: word, view: "" };
}

type Door = (view: AgentsView, word: string) => void;
let take: Door | null = null;
let waiting: [AgentsView, string] | null = null;

/** routes/agents/store.ts registers the one taker; a door that came before it waits for it. */
export function onAgentsView(fn: Door): void {
  take = fn;
  if (waiting) (fn(...waiting), (waiting = null));
}

/** Agents on `view` (`word`: the door it came by; `team`, `fleet` and `runs` show their line the first time). */
export function agentsDoor(view: AgentsView, word = "agents"): void {
  if (take) take(view, word);
  else waiting = [view, word];
}
