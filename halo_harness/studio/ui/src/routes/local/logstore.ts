// Local -> Logs's store (3.3.6.0 R3; studio/local_logs_api.py): the host picked, its log status (GET
// local/host/<n>/log/status), the per-model rows (GET .../log/models), the bounded tail (GET .../log?n=&kind=), the
// kind filter and the Live toggle (a poll every LIVE_MS while it is on and the page is shown; never a stream). Each
// answer is said on its own row (no toast). The host picked is remembered for this browser.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore, writeLocal } from "../../lib/store";

export const LIVE_MS = 5000;
export const TAIL_N = 200;
export const HOST_KEY = "halo.studio.local.logs.host";
export type LogKind = "all" | "fit" | "headroom" | "truncation" | "failure";
export const LOG_KINDS: LogKind[] = ["all", "fit", "headroom", "truncation", "failure"];

export type LogStatus = {
  host: string; state: "live" | "stale" | "quiet" | "unreadable" | "remote-no-ssh" | "missing"; line: string; path: string;
  paths: string[]; last_line_at: number | null; why: string; debug: boolean; readable: boolean; rung: string;
  tail_cli: string; halo_cli: string; debug_action: string; member?: string | null;
};
export type LogLine = { text: string; group: string | null; at: number | null };
export type LogTailAnswer = { host: string; lines: LogLine[]; source: string; why: string | null; n: number; kind: LogKind;
  cli: string; tail_cli: string; path: string };
export type LoadResult = { state: string; line: string; layers: number[] | null; splits: number | null; kv_gpu_mib: number | null;
  kv_cpu_mib: number | null; on_gpu_pct: number | null; tok_s: number | null; window: number | null; at: string | null;
  source: string | null };
export type LogModel = { model: string; load: LoadResult;
  truncations: { at: string; say: string; limit: number | null; prompt: number | null; window_sent: number | null }[];
  errors: { at: string; kind: string; say: string }[];
  crashed: { line: string; signature: string; at: string; count: number } | null };
export type LogModels = { host: string; models: LogModel[]; session: { id: string | null; since: number | null } };

type LogsState = { host: string; status: LogStatus | null; models: LogModels | null; tail: LogTailAnswer | null;
  kind: LogKind; live: boolean; error: string; said: string };

function remembered(): string {
  try {
    return localStorage.getItem(HOST_KEY) || "";
  } catch {
    return "";
  }
}

export const logs = createStore<LogsState>({ host: remembered(), status: null, models: null, tail: null, kind: "all", live: false,
  error: "", said: "" });

export function useLogs<S>(select: (s: LogsState) => S): S {
  return useStore(logs, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const base = (host: string) => `local/host/${encodeURIComponent(host)}/log`;

export async function loadStatus(host: string): Promise<void> {
  try {
    const status = await api.get<LogStatus>(`${base(host)}/status`);
    if (logs.get().host === host) logs.update(() => ({ status, error: "" }));
  } catch (e) {
    logs.update(() => ({ error: msg(e) }));
  }
}

export async function loadModels(host: string): Promise<void> {
  try {
    const models = await api.get<LogModels>(`${base(host)}/models`);
    if (logs.get().host === host) logs.update(() => ({ models }));
  } catch (e) {
    logs.update(() => ({ error: msg(e) }));
  }
}

export async function loadTail(host: string, kind: LogKind = logs.get().kind): Promise<void> {
  try {
    const tail = await api.get<LogTailAnswer>(`${base(host)}?n=${TAIL_N}&kind=${kind}`);
    if (logs.get().host === host && logs.get().kind === kind) logs.update(() => ({ tail }));
  } catch (e) {
    logs.update(() => ({ error: msg(e) }));
  }
}

export function loadAll(host: string): void {
  if (!host) return;
  void loadStatus(host);
  void loadModels(host);
  void loadTail(host);
}

export function pickHost(host: string): void {
  logs.update(() => ({ host, status: null, models: null, tail: null, said: "" }));
  writeLocal(HOST_KEY, host);
  loadAll(host);
}

export function setKind(kind: LogKind): void {
  logs.update(() => ({ kind, tail: null }));
  const host = logs.get().host;
  if (host) void loadTail(host, kind);
}

export function setLive(live: boolean): void {
  logs.update(() => ({ live }));
}

/** The tail command on the clipboard; the row under the block says it (or says to copy it by hand). */
export function copyLine(line: string): void {
  const said = (text: string) => logs.update(() => ({ said: text }));
  if (!line) return;
  try {
    void navigator.clipboard?.writeText(line).then(() => said(`on the clipboard: ${line}`), () => said(`copy it by hand: ${line}`));
  } catch {
    said(`copy it by hand: ${line}`);
  }
}
