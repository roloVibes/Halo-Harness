// The trace of a session's hand-offs (3.6.0.2 R49, R16's "until"): exact and bounded. Every `map_hop` frame is folded,
// as it arrives, into per-session totals -- for each line (or off-line target) how many hand-offs it carried, when the
// last one started and its few words -- and the hand-offs in flight; litStore.ts keeps these apart from its 600-frame
// window of recent frames, so a long session's early hand-offs still count. A line stays live only while its start has no end AND a
// live row carries it, and never once the session is not busy. Pure: `import type` only (tests/test_map_overlay.py runs
// it in node).
import type { OvEvent, OvRow } from "./overlay";
import type { AutoGroup } from "./overlayGroups";

/** One line's count: hand-offs started on it, the last one's time and few words; `off` = the last one was off the map. */
export type HopCount = { n: number; last: number; task: string; off: boolean };
/** `lines` keyed `from>to`; `flight` = the hand-offs started and not ended (their start time); `last` = the newest's key. */
export type Totals = { lines: Record<string, HopCount>; flight: Record<string, number>; last: string };

export const NO_TOTALS: Totals = { lines: {}, flight: {}, last: "" };
const LIVE = ["queued", "running", "paused", "waiting"];
const str = (v: unknown): string => (v == null ? "" : String(v));
const num = (v: unknown): number => (typeof v === "number" && isFinite(v) ? v : 0);

/** One frame folded into the totals (a new object when it changed, the same one when it did not). */
export function foldHop(t: Totals, f: OvEvent): Totals {
  if (f.event !== "map_hop") return t;
  const d = f.data || {};
  const k = `${str(d.from)}>${str(d.to)}`;
  if (d.state === "start") {
    const was = t.lines[k] || { n: 0, last: 0, task: "", off: false };
    return { lines: { ...t.lines, [k]: { n: was.n + 1, last: num(d.t), task: str(d.task), off: !!d.off } },
             flight: { ...t.flight, [k]: num(d.t) }, last: k };
  }
  if (d.state === "end" && k in t.flight) {
    const flight = { ...t.flight };
    delete flight[k];
    return { ...t, flight };
  }
  return t;
}

/** Every frame of a list, folded from nothing (the tests). */
export const foldAll = (frames: OvEvent[], from: Totals = NO_TOTALS): Totals => frames.reduce(foldHop, from);

/** Does a live row carry the hand-off `from>to`: its `crew.line`, the workflow a `workflow:{W}` target names, the agent a
 *  `made-up:{aid}` target names. */
function carried(key: string, rows: OvRow[]): boolean {
  const i = key.indexOf(">");
  const from = key.slice(0, i), to = key.slice(i + 1);
  return rows.some((r) => {
    if (!LIVE.includes(str(r.state))) return false;
    if (to.startsWith("workflow:")) return str(r.crew?.workflow) === to.slice(9);
    if (to.startsWith("made-up:")) return r.agent_id === to.slice(8);
    return str(r.crew?.line) === `${from} -> ${to}`;
  });
}

/** The lines live now: started, not ended, carried by a live row, and the session busy (a fleet load that says it is
 *  not busy ends them all). */
export function inFlight(t: Totals, rows: OvRow[], busy: boolean): Set<string> {
  if (!busy) return new Set();
  return new Set(Object.keys(t.flight).filter((k) => carried(k, rows)));
}

/** 3.6.0.5 B12a: on Auto the drawings read no `map_hop` frame: main's line into group n ("main>group:{n}") is counted from
 *  the group's member rows (n = members started, `last` = the newest member's start, `task` = the group's name) ... */
export function groupTotals(groups: AutoGroup[]): Totals {
  const lines: Record<string, HopCount> = {};
  let last = "", newest = -Infinity;
  for (const g of groups) {
    if (!g.members.length) continue;
    const k = `main>group:${g.n}`, t = Math.max(...g.members.map((m) => m.started || 0));
    lines[k] = { n: g.members.length, last: t, task: g.name, off: false };
    if (t >= newest) (newest = t), (last = k);
  }
  return { lines, flight: {}, last };
}

/** ... and it is live while any member of n is working. */
export const groupLive = (groups: AutoGroup[]): Set<string> =>
  new Set(groups.filter((g) => g.members.some((m) => m.state === "working")).map((g) => `main>group:${g.n}`));
