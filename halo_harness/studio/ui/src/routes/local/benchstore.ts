// Local -> Benchmarks' store (3.3.6.0 R5; studio/local_bench_api.py, studio/local_tune_api.py): the speed cards per
// host (GET local/benches), the bench jobs (POST local/host/<host>/bench starts one, every `bench` frame moves its
// live log, GET local/benches catches up a page that opens while one runs), the tuning report per host (GET
// local/host/<host>/tune; Apply = POST .../tune/apply {id, scope}), and the changes with their scopes (GET
// local/changes; Revert = POST local/changes/revert, a new scope = POST local/changes/scope). Each action's answer
// is said on its own row (no toast). The Bench button first reads the cost line (GET local/host/<host>/bench?model=)
// and shows it as its confirmation.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { loadModels } from "./store";

export type Scope = "session" | "until-restart" | "keep";
export type BenchRow = { window: number; prompt_tok_s: number | null; tok_s: number | null; ttft_ms: number | null;
  size_vram: number | null; size: number | null; layers: number[] | null; on_gpu: boolean | null; error?: string };
export type SpeedCard = { model: string; host: string; ollama_version: string | null; at: number; cold_load_s: number | null;
  windows: BenchRow[]; max_gpu_window: number | null; planner_window: number | null; reserve_floor: number | null;
  quick: boolean; stale: string; lines: string[] };
export type BenchModel = { model: string; size: number | null; card: SpeedCard | null };
export type BenchHost = { name: string; version: string | null; models: BenchModel[] };
export type BenchJob = { job: string; host: string; model: string; quick: boolean; line: string; lines: string[]; done: boolean;
  ok: boolean; error: string | null; started: number; cost: string };
export type ServerLines = Record<string, { set: string; revert: string; restart: string }>;
export type TuneOption = { id: string; line: string; kind: "halo" | "server"; writes: string; takes: string;
  apply: { key: string; field: string; to: unknown }[] | null; server: ServerLines | null; scope_default: Scope | null };
export type TuneReport = { host: string; says: string; warm_set: { line: string; pivots: { line: string }[] } | null;
  models: { model: string; line: string }[]; findings: { id: string; line: string; severity: string }[];
  options: TuneOption[]; os: string | null; cli: string };
export type Change = { id: string; at: string; by: string; host: string; model: string; key: string; field: string; scope: Scope;
  reverted_at: string | null; line: string; scope_words: string; session_id?: string | null };
export type Confirm = { host: string; model: string; cost: string; quick: boolean };

type Bench = { hosts: BenchHost[] | null; jobs: Record<string, BenchJob>; reports: Record<string, TuneReport>;
  changes: Change[] | null; said: Record<string, { ok: boolean; text: string }>; confirm: Confirm | null; error: string };
export const bench = createStore<Bench>({ hosts: null, jobs: {}, reports: {}, changes: null, said: {}, confirm: null, error: "" });

export function useBench<S>(select: (s: Bench) => S): S {
  return useStore(bench, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const say = (k: string, ok: boolean, text: string) => bench.update((s) => ({ said: { ...s.said, [k]: { ok, text } } }));
export const benchLine = (host: string, model: string, quick = false) => `halo local bench --host ${host} --model ${model}${quick ? " --quick" : ""}`;

function take(j: BenchJob): void {
  const before = bench.get().jobs[j.job];
  bench.update((s) => ({ jobs: { ...s.jobs, [j.job]: { ...(s.jobs[j.job] || {}), ...j } } }));
  if (j.done && !(before && before.done)) {
    void loadBenches();
    if (j.ok) void loadModels();
  }
}

/** The newest bench job for this host and model (running first). */
export function jobFor(s: Bench, host: string, model: string): BenchJob | undefined {
  const all = Object.values(s.jobs).filter((j) => j.host === host && j.model === model);
  return all.find((j) => !j.done) || all.sort((a, b) => b.started - a.started)[0];
}

export async function loadBenches(): Promise<void> {
  try {
    const r = await api.get<{ hosts: BenchHost[]; jobs: BenchJob[] }>("local/benches");
    bench.update(() => ({ hosts: r.hosts || [], error: "" }));
    for (const j of r.jobs || []) take(j);
  } catch (e) {
    bench.update(() => ({ error: msg(e) }));
  }
}

/** The Bench button: read the cost line first, shown as the confirmation. */
export async function askBench(host: string, model: string, quick = false): Promise<void> {
  const k = `${host}|${model}`;
  try {
    const r = await api.get<{ cost: string }>(`local/host/${encodeURIComponent(host)}/bench?model=${encodeURIComponent(model)}${quick ? "&quick=1" : ""}`);
    bench.update(() => ({ confirm: { host, model, cost: r.cost, quick } }));
    say(k, true, "");
  } catch (e) {
    say(k, false, msg(e));
  }
}

export async function startBench(host: string, model: string, quick = false): Promise<void> {
  const k = `${host}|${model}`;
  bench.update(() => ({ confirm: null }));
  try {
    take(await api.post<BenchJob>(`local/host/${encodeURIComponent(host)}/bench`, { model, quick }));
    say(k, true, "");
  } catch (e) {
    say(k, false, msg(e));
  }
}

export function cancelConfirm(): void {
  bench.update(() => ({ confirm: null }));
}

export async function loadTune(host: string): Promise<void> {
  try {
    const r = await api.get<TuneReport>(`local/host/${encodeURIComponent(host)}/tune`);
    bench.update((s) => ({ reports: { ...s.reports, [host]: r } }));
  } catch (e) {
    say(`tune|${host}`, false, msg(e));
  }
}

export async function applyOption(host: string, id: string, scope: Scope): Promise<void> {
  try {
    const r = await api.post<{ lines: string[] }>(`local/host/${encodeURIComponent(host)}/tune/apply`, { id, scope });
    say(`opt|${id}`, true, (r.lines || []).join(" · "));
    void loadChanges();
    void loadTune(host);
  } catch (e) {
    say(`opt|${id}`, false, msg(e));
  }
}

export async function applyChange(key: string, field: string, to: unknown, scope: Scope, why: string, said: string): Promise<boolean> {
  try {
    const r = await api.post<{ line: string }>("local/changes/apply", { key, field, to, scope, why });
    say(said, true, r.line);
    void loadChanges();
    return true;
  } catch (e) {
    say(said, false, msg(e));
    return false;
  }
}

export async function loadChanges(): Promise<void> {
  try {
    const r = await api.get<{ changes: Change[] }>("local/changes");
    bench.update(() => ({ changes: r.changes || [] }));
  } catch (e) {
    bench.update(() => ({ error: msg(e) }));
  }
}

export async function revertChange(id: string): Promise<void> {
  try {
    const r = await api.post<{ lines: string[] }>("local/changes/revert", { id });
    say("chg|last", true, (r.lines || []).join(" · ")); // the row goes; the list says what was put back
    void loadChanges();
    void loadModels();
  } catch (e) {
    say("chg|last", false, msg(e));
  }
}

export async function rescope(id: string, scope: Scope): Promise<void> {
  try {
    const r = await api.post<{ line: string }>("local/changes/scope", { id, scope });
    say(`chg|${id}`, true, r.line);
    void loadChanges();
  } catch (e) {
    say(`chg|${id}`, false, msg(e));
  }
}

let live = false;

/** Once: the `bench` frames. */
export function startBenchFeed(): void {
  if (live) return;
  live = true;
  onEvent("bench", (f) => {
    const j = f.data as BenchJob | undefined;
    if (j && j.job) take(j);
  });
}
