// Local -> Pool, the running pool's store (3.3.8.0 R3; studio/pool_act_api.py): the run (GET local/pool/run: running /
// loading / degraded / down / stopped, each member's claim and its lease, the Warm in progress, the 10 min cooldown),
// the preflight of the model picked (GET local/pool/preflight: Warm is enabled only when it is green), and the actions
// -- Warm (POST local/pool/warm: 202, then the run says how it went), Stop (POST local/pool/stop). The run is read
// every RUN_MS while the page is open (BUSY_MS while a Warm runs); the preflight when the model or the Wi-Fi switch
// changes and after every action.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";

export const RUN_MS = 10_000;
export const BUSY_MS = 1_500;

export type Check = { check: string; ok: boolean; lines: string[] };
export type Preflight = { ok: boolean; model: string; display: string; checks: Check[]; blocks: string[]; line: string;
  used: string[]; excluded: string[]; ctx: number; q8: boolean; cache: string; allow_wifi: boolean; order: string[];
  split: number[]; cli: string };
export type Claim = { gb: number; until: number | null; live: boolean | null; line: string };
export type RunMember = { name: string; kind: string; share_gb: number | null; alive: boolean | null; addr: string | null;
  claim: Claim };
export type Run = { state: "stopped" | "loading" | "running" | "degraded" | "down"; line: string; lines: string[];
  members: RunMember[]; degraded: string[]; log?: string[]; run: { model?: string; display?: string; url?: string;
  ctx?: number; cache?: string } ; warm: { busy?: boolean; model?: string; ok?: boolean | null; lines?: string[] };
  cooldown: string; cli: string };
type Said = { ok: boolean; text: string };
type RunState = { run: Run | null; pf: Preflight | null; model: string; wifi: boolean; busy: string; error: string;
  said: Record<string, Said> };

export const poolRun = createStore<RunState>({ run: null, pf: null, model: "", wifi: false, busy: "", error: "", said: {} });

export function usePoolRun<S>(select: (s: RunState) => S): S {
  return useStore(poolRun, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const say = (k: string, s: Said) => poolRun.update((st) => ({ said: { ...st.said, [k]: s } }));

export async function loadRun(): Promise<void> {
  try {
    const run = await api.get<Run>("local/pool/run");
    poolRun.update(() => ({ run, error: "" }));
  } catch (e) {
    poolRun.update(() => ({ error: msg(e) }));
  }
}

export async function loadPreflight(): Promise<void> {
  const { model, wifi } = poolRun.get();
  if (!model) return;
  try {
    const pf = await api.get<Preflight>("local/pool/preflight", { model, ...(wifi ? { allow_wifi: 1 } : {}) });
    poolRun.update(() => ({ pf }));
  } catch (e) {
    poolRun.update(() => ({ pf: null }));
    say("preflight", { ok: false, text: msg(e) });
  }
}

export function pickModel(model: string): void {
  if (model === poolRun.get().model) return;
  poolRun.update(() => ({ model, pf: null }));
  void loadPreflight();
}

export function setWifi(on: boolean): void {
  poolRun.update(() => ({ wifi: on }));
  void loadPreflight();
}

export async function warmNow(): Promise<void> {
  const { model, wifi } = poolRun.get();
  poolRun.update(() => ({ busy: "warm" }));
  try {
    const r = await api.post<{ cli: string }>("local/pool/warm", { model, allow_wifi: wifi });
    say("warm", { ok: true, text: `Warm started (${r.cli})` });
  } catch (e) {
    say("warm", { ok: false, text: msg(e) });
  } finally {
    poolRun.update(() => ({ busy: "" }));
    void loadRun();
  }
}

export async function stopNow(): Promise<void> {
  poolRun.update(() => ({ busy: "stop" }));
  try {
    const r = await api.post<{ lines: string[] }>("local/pool/stop", {});
    say("stop", { ok: true, text: (r.lines || []).join(" · ") });
  } catch (e) {
    say("stop", { ok: false, text: msg(e) });
  } finally {
    poolRun.update(() => ({ busy: "" }));
    void loadRun();
    void loadPreflight();
  }
}
