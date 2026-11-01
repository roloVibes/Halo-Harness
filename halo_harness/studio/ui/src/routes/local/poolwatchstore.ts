// Local -> Pool, the measured half's store (3.3.8.0 R4; studio/pool_watch_api.py): the bench (GET local/pool/bench:
// the cost line first -- seconds, the members busy for them -- the pool's speed card, its penalty line, the bundles
// that hold the pool; POST local/pool/bench runs it in the background, the GET says how it went) and the steward's
// pool findings (GET local/pool/findings: pool-degraded, pool-rtt, pool-spill, one line each). Read when the page
// opens, every WATCH_MS while it is open, every BUSY_MS while a bench runs.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";

export const WATCH_MS = 15_000;
export const BUSY_MS = 1_000;

export type Estimate = { seconds: number; windows: number[]; line: string };
export type Card = { model: string; host: string; members: string[]; split: number[]; cache: string; ctx: number;
  cold_load_s: number | null; at: number; reserve_floor: number | null; verified_by?: string | null; lines: string[] };
export type Speed = { word: string; measured: boolean; tok_s: number | null; penalty_pct: number; penalty_from: string;
  vs: string | null; stale: string };
export type BenchRun = { busy?: boolean; ok?: boolean | null; lines?: string[]; say?: string };
export type Held = { bundle: string; model: string | null; priority: string | null; hours: string | null; gb: number };
export type Bench = { estimate: Estimate | null; card: Card | null; speed: Speed | null; bench: BenchRun; held: Held[];
  cli: string };
export type Finding = { id: string; rule: string; severity: string; finding: string; key: string; model: string };
type Said = { ok: boolean; text: string };
type WatchState = { bench: Bench | null; findings: Finding[] | null; error: string; said: Said | null; busy: boolean };

export const poolWatch = createStore<WatchState>({ bench: null, findings: null, error: "", said: null, busy: false });

export function usePoolWatch<S>(select: (s: WatchState) => S): S {
  return useStore(poolWatch, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

export async function loadBench(): Promise<void> {
  try {
    const bench = await api.get<Bench>("local/pool/bench");
    poolWatch.update(() => ({ bench, error: "" }));
  } catch (e) {
    poolWatch.update(() => ({ error: msg(e) }));
  }
}

export async function loadFindings(): Promise<void> {
  try {
    const r = await api.get<{ findings: Finding[] }>("local/pool/findings");
    poolWatch.update(() => ({ findings: r.findings }));
  } catch (e) {
    poolWatch.update(() => ({ error: msg(e) }));
  }
}

export async function benchNow(quick: boolean): Promise<void> {
  poolWatch.update(() => ({ busy: true, said: null }));
  try {
    const r = await api.post<{ cli: string }>("local/pool/bench", { quick });
    poolWatch.update(() => ({ said: { ok: true, text: `Bench started (${r.cli})` } }));
  } catch (e) {
    poolWatch.update(() => ({ said: { ok: false, text: msg(e) } }));
  } finally {
    poolWatch.update(() => ({ busy: false }));
    void loadBench();
  }
}
