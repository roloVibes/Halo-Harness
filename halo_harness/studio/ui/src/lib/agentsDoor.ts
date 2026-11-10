// 3.3.16.0 R1 "Agents: one section": Team, Roles and Orchestra fold into Agents (Alt+2), one section with three views --
// Cast (the lineup and its bios: Roles' canvas), Runs (Orchestra: a goal, the lead's plan, the lanes, the report) and
// Live (Roles Live: the session's agents as a tree). The three old words stay doors: `?mode=roles` lands on Cast
// (`&view=live` on Live), `?mode=orchestra` and `?mode=team` on Runs (Team's with one line, the first time in this
// browser); `?mode=agents&view=cast|runs|live` is the door itself. A saved section, a `focus` frame, an attention
// row's `o` and a pack's route that name an old word land the same way (lib/store.ts goSection). routes/agents/store.ts
// takes the view (onAgentsView); this file has no React and no store of its own, so lib/store.ts may import it.
// 3.3.16.0 R2 "the Fleet fold": `fleet` is a door too -- Agents on Live with the fleet scope on (`?scope=fleet`: every
// machine, its sessions, their agents), on Runs when it names a mission (`?mode=fleet&mission=<id>`); its line once.
// 3.3.16.0 R3: `workflows` -- the board of squares (`?mode=agents&view=workflows`, W).
export type AgentsView = "cast" | "runs" | "live" | "workflows";
export type LiveScope = "here" | "fleet";
export const AGENTS_VIEWS: AgentsView[] = ["cast", "runs", "live", "workflows"];
/** The words of the sections Agents took in, and the view each one lands on. */
export const AGENTS_DOORS: Record<string, AgentsView> = { roles: "cast", orchestra: "runs", team: "runs", fleet: "live" };
export const TEAM_NOTE = "Team's board is gone; a run's plan shows who owns what";
export const FLEET_NOTE = "Fleet is Agents -> Live now: machines in Setup -> Machines, models in Local";

const isView = (v: string): v is AgentsView => (AGENTS_VIEWS as string[]).includes(v);

function query(search?: string): URLSearchParams | null {
  try {
    return new URLSearchParams(search ?? location.search);
  } catch {
    return null;
  }
}

/** The view a page's URL asks Agents for, and the word it came by ('' when the URL names none of Agents' doors). */
export function urlDoor(search?: string): { view: AgentsView | ""; word: string } {
  const q = query(search);
  if (!q) return { view: "", word: "" };
  const word = q.get("mode") || "";
  const view = q.get("view") || "";
  if (word === "agents") return { view: isView(view) ? view : "cast", word };
  if (word === "roles") return { view: view === "live" ? "live" : "cast", word };
  if (word === "fleet") return { view: q.get("mission") ? "runs" : "live", word };
  return { view: AGENTS_DOORS[word] || "", word: AGENTS_DOORS[word] ? word : "" };
}

/** The scope a page's URL asks Live for: `?scope=fleet|here`, or the fleet for `?mode=fleet` ('' = Live decides). */
export function urlScope(search?: string): LiveScope | "" {
  const q = query(search);
  const s = q?.get("scope") || "";
  if (s === "fleet" || s === "here") return s;
  return q?.get("mode") === "fleet" ? "fleet" : "";
}

/** The mission a page's URL names (`?mode=fleet&mission=<id>`, `?mode=agents&view=runs&mission=<id>`), else ''. */
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

/** Agents on `view` (`word`: the door it came by; `team` and `fleet` show their line the first time). */
export function agentsDoor(view: AgentsView, word = "agents"): void {
  if (take) take(view, word);
  else waiting = [view, word];
}
