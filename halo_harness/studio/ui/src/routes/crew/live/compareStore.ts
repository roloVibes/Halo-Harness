// Compare two runs (3.4.1.0 R2 "Time"): History's ticks and the comparison its Compare page shows. Tick two rows -- a
// session, a goal run, a saved replay file -- and Compare reads `GET replays/compare?a=&b=` (live/compare.py: the two
// runs' figures from their own records, the rows with the better figure named by a word, three "what differed" lines,
// each agent as a lane of phase segments). One row ticked compares it with itself before / after a moment (its first
// steer, else halfway; the page's "split at" moves it). A mission is the fleet pack's: it is compared from its report.
// The rows are plain data (`CmpRow`): the run report card shows the same cells for one run.
import { api, ApiError } from "../../../lib/api";
import { createStore, useStore } from "../../../lib/store";
import type { HistoryRow } from "./historyStore";

export type Cell = { value: unknown; text: string; unknown?: boolean };
export type CmpRow = { key: string; label: string; a: Cell; b: Cell; better: "a" | "b" | "same" | null; word: string };
export type Seg = { t0: number; t1: number; phase: string };
export type CmpLane = { agent_id: string; name: string; role: string; model: string; block: string; state: string; from: number; to: number; segs: Seg[] };
export type Side = { label: "A" | "B"; kind: string; id: string; file: string | null; title: string; started: number | null;
  figures: { wall_s: number | null; window: number[] | null; how: string }; lanes: CmpLane[] };
export type Comparison = { a: Side; b: Side; rows: CmpRow[]; differed: string[]; split: number | null; axis: { secs: number } };

type State = { ticked: string[]; refs: [string, string] | null; split: number | null; data: Comparison | null; error: string };
export const compare = createStore<State>({ ticked: [], refs: null, split: null, data: null, error: "" });
export const useCompare = <S,>(pick: (s: State) => S): S => useStore(compare, pick);

/** A History row's tick, and the ref the server reads ("<kind>:<id>"; a mission's is left out of Compare). */
export const tickKey = (r: Pick<HistoryRow, "kind" | "id">): string => `${r.kind}:${r.id}`;

/** Tick or untick a row; a third tick lets the oldest go (two at most). */
export function toggleTick(key: string): void {
  compare.update((s) => ({ ticked: s.ticked.includes(key) ? s.ticked.filter((k) => k !== key) : [...s.ticked, key].slice(-2) }));
}

/** The refs Compare reads from the ticks. */
export function tickedRefs(ticked: string[]): { refs: string[] } {
  return { refs: ticked };
}

let asking = 0;
/** Read the comparison of `a` and `b` (the same ref twice: before / after `split` seconds). */
export async function loadCompare(a: string, b: string, split: number | null = null): Promise<void> {
  const mine = ++asking;
  compare.update(() => ({ refs: [a, b], split, data: null, error: "" }));
  try {
    const data = await api.get<Comparison>("replays/compare", { a, b, ...(split !== null ? { split: String(split) } : {}) });
    if (mine === asking) compare.update(() => ({ data, split: data.split }));
  } catch (e) {
    if (mine === asking) compare.update(() => ({ error: e instanceof ApiError ? e.message : String(e) }));
  }
}

export const clearCompare = () => compare.update((s) => (s.refs ? { refs: null, data: null, error: "", split: null } : {}));
