// Which session Session draws and speaks of (3.6.0.2 R1, R4, R5). Pure: `import type` only, so tests/helpers/node_ts.py
// runs it (tests/test_studio_session_map_down.py). The pick (the scope's session) wins while it is open; with no pick, the
// newest OPEN session (a terminal one with no turn included), never a Studio-started one with no message yet (T10) while
// another is open. A picked session that ends is kept (its last row, and when it went: T8) until another is picked.
// 3.6.0.11: only a pick he made by hand is kept; one the page made follows the newest open session (`autoPick`).
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

const hashes = new Map<string, { hash: string; t: number | null }>(); // R20 T5: when a session's map content changed
let next: { b: string | null; none: boolean } | null = null; // R4: the map new sessions use (none: no map), as this page last heard it

/** Note the open rows (each fleet change): a session seen before and now without a row has ended at `now`; a row whose
 *  `map_hash` differs from the one this page first saw took a changed map at `now` (T5). */
export function noteRows(rows: SessionRow[], now: number): void {
  const here = new Set(rows.map((r) => r.session_id));
  for (const r of rows) (seen.set(r.session_id, r), gone.delete(r.session_id));
  for (const sid of seen.keys()) if (!here.has(sid) && !gone.has(sid)) gone.set(sid, now);
  for (const r of rows) noteHash(r, now);
  const top = openOrder(rows.filter((r) => "map_next" in r))[0];
  if (top) next = { b: top.map_next || null, none: !top.map_next && !!top.map_next_none };
}

/** T5: the first `map_hash` seen of a session, then when a different one was first seen (whoever reads the row first). */
function noteHash(r: SessionRow, now: number): { hash: string; t: number | null } | undefined {
  const h = r.map_hash ? String(r.map_hash) : "", k = hashes.get(r.session_id);
  if (h && !k) hashes.set(r.session_id, { hash: h, t: null });
  else if (h && k && k.hash !== h) hashes.set(r.session_id, { hash: h, t: now });
  return hashes.get(r.session_id);
}

/** R4: a Builder card applied in a session (`builder_done`): the map it wrote and the map new sessions use after it. */
type Build = { sid: string; map: string; t: number };
let build: Build | null = null;
export function noteBuild(sid: string, d: Record<string, unknown>, now: number): void {
  if (!sid || d.outcome !== "applied") return;
  const wrote = (Array.isArray(d.wrote) ? d.wrote : []) as { kind?: string; name?: string }[];
  const m = wrote.find((w) => w && w.kind === "map" && w.name);
  if ("next" in d) next = { b: typeof d.next === "string" && d.next ? d.next : null, none: !d.next && d.next_none === true };
  if (m) build = { sid, map: String(m.name), t: Number(d.t) || now };
  const maps = d.maps && typeof d.maps === "object" ? (d.maps as Record<string, unknown>) : {};
  for (const [n, b] of Object.entries(maps)) if (b && typeof b === "object") bodies.set(n, b as MapBody); // T7: the newest body
}

/** R22 T7: a map's body as this page last had it (a builder_done frame's `maps`, else the one read; false while that
 *  read is out); undefined when it has none. */
export type MapBody = { boxes?: { workflow?: string }[] };
const bodies = new Map<string, MapBody | false>();
export const mapBody = (name: string): MapBody | false | undefined => bodies.get(name);
/** The read of a body: asked (false), answered (the body), failed (null: forgotten, so it is read again next time). */
export function noteBody(name: string, body: MapBody | false | null): void {
  if (body === null) bodies.delete(name);
  else bodies.set(name, body);
}

/** R4's Start view: the last build this page heard from a session that is not open any more (it ended), else null. */
export function lastBuild(rows: SessionRow[]): { map: string; t: number } | null {
  return build && !rows.some((r) => r.session_id === build!.sid) ? { map: build.map, t: build.t } : null;
}

/** {B} as this page last heard it (the newest row's `map_next`, a build's `next`); undefined when it heard neither. */
export function knownNext(): { b: string | null; none: boolean } | undefined {
  return next || undefined;
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

let listSeen = -1;
/** R1: `staleRead`, counted once per fresh read of the session LIST (`reads`: the fleet's `listReads`, bumped by GET live's
 *  answer and a sessions frame), never per agent frame of another session (those change the rows, not the list read). */
export function staleList(reads: number, rows: SessionRow[], pick: string): boolean {
  const fresh = reads !== listSeen;
  listSeen = reads;
  return fresh && !!pick && staleRead(rows, pick);
}

/** R4: reads that may be answered out of order: each call of the returned `read` sends one read with its own number, and
 *  only the answer (or the failure) of the newest read is kept; an older answer that lands late is dropped. */
export function newestOnly<T>(get: () => Promise<T>, keep: (v: T) => void, fail: () => void): () => void {
  let n = 0;
  return () => {
    const mine = ++n;
    get().then((v) => void (mine === n && keep(v)), () => void (mine === n && fail()));
  };
}

/** R1: the picked row while it is open; a pick is never another session: one that ended (null here, T8 in the drawer)
 *  or one not listed yet (New session registers a moment later) is null; with no pick the newest open row that is not
 *  T10, else (only T10 rows are open) the newest of those. */
export function livePick<R extends SessionRow>(rows: R[], pick: string): R | null {
  if (pick) return rows.find((x) => x.session_id === pick) || null;
  return openOrder(rows)[0] || null;
}

/** 3.6.0.11 (the owner: "The session gui view doesn't synch with the terminal"): the pick after a fresh read of the
 *  list. A pick he did not make by hand follows the newest open session (`openOrder`), so one that ended moves to it
 *  too; a hand pick never moves by itself, and nothing moves while the Prompt box holds text. Nothing open: it stays. */
export function autoPick<R extends SessionRow>(rows: R[], pick: string, byHand: boolean, holdsText: boolean): string {
  if (byHand || holdsText) return pick;
  return openOrder(rows)[0]?.session_id || pick;
}

/** 3.6.0.11: an agent he chose makes the pick his (the ruling: "a Map or agent selection"): one he selected on harness
 *  `here` (`sel`, not the one the store selected itself: `own`), a pin or a steer target (their session stays shown,
 *  so the Feed's head and the Steer box never speak of two sessions). */
export const hisAgent = (here: string, sel: string, own: string, pin: string, target: string): boolean =>
  !!pin || !!target || (!!sel && sel !== own && sel.startsWith(`${here}|`));

let steerDraft = ""; // the Feed's Steer box's unsent text (LiveSteer.tsx): kept for the next open; while the box is open it holds a move
export const noteSteerDraft = (t: string): void => void (steerDraft = t);
export const steerText = (): string => steerDraft;

let autoTo = ""; // the session autoPick last moved Session to (the Feed's head says the move: FeedSession.tsx)
export const noteAutoMove = (sid: string): void => void (autoTo = sid);
export const autoMovedTo = (sid: string): boolean => !!sid && autoTo === sid;

/** 3.6.0.11: the Feed's lines: the shown session's only (its key prefix); with none shown, every line of harness `here`. */
export const feedOf = (here: string, sid: string) => (l: { key: string }): boolean => l.key.startsWith(sid ? `${here}|${sid}|` : `${here}|`);

const heirs = new Map<string, string>(); // 3.6.0.2 P31: a pick moved by `follows`: the new id -> the old pick

/** 3.6.0.2 P31: the open row that took over from `pick` once `pick` left the list (its `follows` names the pick, or
 *  names a row that did: /clear twice, read through the rows this page saw), else null (`pick` still listed, or nothing
 *  follows it: P32). A move found here is remembered for `followedFrom` (the header's line). */
export function followerOf<R extends SessionRow>(rows: R[], pick: string): R | null {
  if (!pick || rows.some((r) => r.session_id === pick)) return null;
  const known = [...rows, ...seen.values()];
  const walked = new Set<string>();
  for (let at = pick; at && !walked.has(at); ) {
    walked.add(at);
    const next = known.find((r) => r.follows === at && !walked.has(r.session_id));
    if (!next) return null;
    const open = rows.find((r) => r.session_id === next.session_id);
    if (open) return (heirs.set(open.session_id, pick), open);
    at = next.session_id;
  }
  return null;
}

/** P31: the pick `sid` took over from by `follows` ("" when it was picked any other way). */
export const followedFrom = (sid: string): string => heirs.get(sid) || "";

let listChose = ""; // P28: the pick `Change session` just set (P29's line is for every other change)
/** P28: `Change session` chose `sid` while `pick` is picked. The session already picked changes nothing, so it is not
 *  remembered (else a later move back to it by the Map or `/studio` would pass for the list's and show no line). */
export function choseInList(sid: string, pick: string): void {
  listChose = sid === pick ? "" : sid;
}
/** P29: did the list set this new pick? Asked once per change of pick; the answer is used up either way. */
export function tookFromList(pick: string): boolean {
  const chose = !!pick && listChose === pick;
  listChose = "";
  return chose;
}

/** What the truth sentence knows of an open row (P2's status row fields); never `busy` for the words. */
export function factsOf(row: SessionRow, ended: number | null = null, now = Date.now() / 1000): TruthFacts {
  const asked = !!row.asked || !!Number(row.turns);
  const hash = ended ? hashes.get(row.session_id) : noteHash(row, now); // a render may read the row before noteRows
  return {
    title: String(row.title || row.session_id.slice(0, 8)), a: typeof row.map === "string" && row.map ? row.map : null,
    plain: !!row.map_plain, b: row.map_next || null, bNone: !row.map_next && !!row.map_next_none, bSince: row.map_next_since ?? null,
    started: Number(row.map_since || row.started) || 0, turns: asked ? Math.max(1, Number(row.turns) || 0) : 0,
    studio: String(row.parent || "").startsWith("studio:"), ended, machine: null, unreadable: null,
    changed: hash?.t ? { t: hash.t } : null,
    workflow: null, busy: !!row.busy, flowsCan: Array.isArray(row.map_flows) ? row.map_flows.map(String) : [],
  };
}
