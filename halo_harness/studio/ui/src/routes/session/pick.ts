// Which session Session draws and speaks of (3.6.0.2 R1, R4, R5). Pure: `import type` only, so tests/helpers/node_ts.py
// runs it (tests/test_studio_session_map_down.py). The pick (the scope's session) wins while it is open; with no pick, the
// newest OPEN session (a terminal one with no turn included), never a Studio-started one with no message yet (T10) while
// another is open. A picked session that ends is kept (its last row, and when it went: T8) until another is picked.
import type { SessionRow } from "../fleet/types";
import type { TruthFacts } from "../crew/map/truth";

/** R5: a session Studio started (`parent` = `studio:<pid>`) that has had no message yet (a /clear keeps `asked`). */
export function isStudioIdle(row: Pick<SessionRow, "parent" | "turns" | "asked">): boolean {
  return String(row.parent || "").startsWith("studio:") && !Number(row.turns) && !row.asked;
}

/** The open sessions newest first, every T10 one last (Session's default, Agents -> Live's picker). */
export function openOrder<R extends SessionRow>(rows: R[]): R[] {
  const by = (x: R, y: R) => (Number(y.started) || 0) - (Number(x.started) || 0) || (x.session_id < y.session_id ? -1 : 1);
  return [...rows.filter((r) => !isStudioIdle(r)).sort(by), ...rows.filter(isStudioIdle).sort(by)];
}

const seen = new Map<string, SessionRow>(); // the last row of each session this page saw
const gone = new Map<string, number>(); // when a seen session's row went (it ended), epoch seconds

/** Note the open rows (each fleet change): a session seen before and now without a row has ended at `now`. */
export function noteRows(rows: SessionRow[], now: number): void {
  const here = new Set(rows.map((r) => r.session_id));
  for (const r of rows) (seen.set(r.session_id, r), gone.delete(r.session_id));
  for (const sid of seen.keys()) if (!here.has(sid) && !gone.has(sid)) gone.set(sid, now);
}

/** R4: the picked session that ended: its last row and when it went (T8), else null. */
export function lastRow(sid: string): { row: SessionRow; ended: number } | null {
  const row = seen.get(sid);
  const t = gone.get(sid);
  return row && t ? { row, ended: t } : null;
}

const mine = new Set<string>(); // sessions this page started (New session): their pick waits for them to register
const misses = new Map<string, number>(); // reads in a row that did not list a pick this page never saw

/** New session: this page asked for `sid`, so a pick of it is held until it registers (never given up). */
export function startedHere(sid: string): void {
  if (sid) mine.add(sid);
}

/** R1, one read of the open rows (GET live, a sessions frame): true once a pick this page never saw listed and did not
 *  start is missing from two reads in a row (a `?session=` link or a "Watch in Session" link to a session that ended
 *  before the page loaded): the pick is given up and Session shows what it would with no pick. */
export function staleRead(rows: SessionRow[], pick: string): boolean {
  if (!pick || seen.has(pick) || mine.has(pick) || rows.some((r) => r.session_id === pick)) return (misses.delete(pick), false);
  const n = (misses.get(pick) || 0) + 1;
  if (n < 2) return (misses.set(pick, n), false);
  misses.delete(pick);
  return true;
}

/** R1: the picked row while it is open; a pick is never another session: one that ended (null here, T8 in the drawer)
 *  or one not listed yet (New session registers a moment later) is null; with no pick the newest open row that is not
 *  T10, else (only T10 rows are open) the newest of those. */
export function livePick<R extends SessionRow>(rows: R[], pick: string): R | null {
  if (pick) return rows.find((x) => x.session_id === pick) || null;
  return openOrder(rows)[0] || null;
}

/** What the truth sentence knows of an open row (P2's status row fields); never `busy` for the words. */
export function factsOf(row: SessionRow, ended: number | null = null): TruthFacts {
  const asked = !!row.asked || !!Number(row.turns);
  return {
    title: String(row.title || row.session_id.slice(0, 8)), a: typeof row.map === "string" && row.map ? row.map : null,
    plain: !!row.map_plain, b: row.map_next || null, bSince: row.map_next_since ?? null,
    started: Number(row.map_since || row.started) || 0, turns: asked ? Math.max(1, Number(row.turns) || 0) : 0,
    studio: String(row.parent || "").startsWith("studio:"), ended, machine: null, unreadable: null, changed: null,
    workflow: null, busy: !!row.busy,
  };
}
