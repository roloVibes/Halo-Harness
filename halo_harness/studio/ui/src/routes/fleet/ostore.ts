// The Ollama panel's store (3.3.4.0 R5; studio/ollama_steward_api.py): `GET ollama/steward` (the job's status,
// the notes, the mode, the pending proposals and the changes in place), `GET ollama/hosts` (per host the card,
// the models, the findings, the fit plan; the Hugging Face local servers) and `GET ollama/timeline` (the
// ledger per minute). Live through the job's `steward` frames; a job in another process (the hub, `--watch`)
// sends none, so the panel also refetches every REFRESH_MS while it is open. Settings and Setup read the
// steward's status from here too.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, toast, useStore } from "../../lib/store";

export const REFRESH_MS = 30_000;

export type Note = { id: string; at: string; stage: string; say: string; lines?: string[]; cost?: string | null; model?: string | null; attention?: boolean };
export type Change = { id: string; at: string; kind: string; key: string; field: string; from?: unknown; to: unknown; why?: string; say?: string; finding?: string; rule?: string };
export type Proposal = { field: string; from?: unknown; to: unknown; why: string };
export type Hint = { env?: string | null; line: string; cost: string };
export type Finding = {
  id: string; rule: string; host: string; model: string; key: string; severity: string; finding: string;
  evidence: { numbers?: Record<string, unknown>; calls?: string[]; events?: string[] };
  proposal: Proposal | null; server_hint: Hint | null; applied: string | null; proposed: boolean;
};
export type PlanOption = { kind: string; says: string; changes: { key: string; field: string; to: unknown }[]; server_hint: Hint | null; lose: string; fits: boolean };
export type Plan = { host: string; says: string; fits_now: boolean | null; chosen: number | null; models: { model: string; window: number; need: number | null }[]; options: PlanOption[]; missing: string[] };
export type Hour = { calls: number; trims: number; cuts: number; reloads: number; errors: number; p95_prompt: number | null; window: number | null; p95_pct: number | null };
export type ModelRow = {
  model: string; vision: boolean; day_calls: number; hour: Hour | null;
  loaded: { size: number | null; size_vram: number | null; vram_pct: number | null; expires: string | null; context_length: number | null } | null;
  profile: { num_ctx?: number; num_predict?: number; keep_alive?: string | number; by?: string; note?: string; at?: string } | null;
};
export type HostView = { name: string; url: string; served_here: boolean; card_lines: string[]; models: ModelRow[]; findings: Finding[]; plan: Plan | null; kind?: string };
export type Hosts = { hosts: HostView[]; local_servers: HostView[]; mode: string; at: number };
export type Status = { running?: boolean; where?: string; since?: number; machine?: string; model?: string | null; model_why?: string; last_run?: { at: number; mode: string; findings: number; applied: number; proposed: number } };
export type Steward = { status: Status; status_lines: string[]; notes: Note[]; last_note: Note | null; hub_note: { hub?: string; line: string; at?: string } | null; mode: string; models: string[]; changes: Change[]; proposals: Change[] };
export type Bucket = { t: number; calls: number; trims: number; cuts: number; errors: number; p95_prompt: number | null };

type OllamaState = {
  steward: Steward | null;
  hosts: Hosts | null;
  timeline: Record<string, Bucket[]>;
  host: string;
  error: string;
  busy: string;
  copied: string;
};

export const ollama = createStore<OllamaState>({ steward: null, hosts: null, timeline: {}, host: "", error: "", busy: "", copied: "" });

export function useOllama<S>(select: (s: OllamaState) => S): S {
  return useStore(ollama, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

export async function loadSteward(): Promise<void> {
  try {
    const steward = await api.get<Steward>("ollama/steward");
    ollama.update(() => ({ steward, error: "" }));
  } catch (e) {
    ollama.update(() => ({ error: msg(e) }));
  }
}

export async function loadHosts(): Promise<void> {
  try {
    const hosts = await api.get<Hosts>("ollama/hosts");
    ollama.update((s) => {
      const names = [...hosts.hosts, ...hosts.local_servers].map((h) => h.name);
      return { hosts, error: "", host: names.includes(s.host) ? s.host : names[0] || "" };
    });
  } catch (e) {
    ollama.update(() => ({ error: msg(e) }));
  }
}

export async function loadTimeline(host: string): Promise<void> {
  if (!host) return;
  try {
    const r = await api.get<{ buckets: Bucket[] }>("ollama/timeline", { host, since: "1h" });
    ollama.update((s) => ({ timeline: { ...s.timeline, [host]: r.buckets || [] } }));
  } catch {
    /* the panel draws without the sparkline */
  }
}

export function loadAll(): void {
  void loadSteward();
  void loadHosts().then(() => void loadTimeline(ollama.get().host));
}

export function pickHost(host: string): void {
  ollama.update(() => ({ host }));
  void loadTimeline(host);
}

async function act(what: string, path: string, body: Record<string, unknown>, done: string): Promise<boolean> {
  ollama.update(() => ({ busy: what }));
  try {
    const r = await api.post<{ say?: string }>(path, body);
    toast(r.say || done, "done", 4000);
    loadAll();
    return true;
  } catch (e) {
    toast(msg(e), "error", 6000);
    return false;
  } finally {
    ollama.update(() => ({ busy: "" }));
  }
}

export const applyFinding = (id: string) => act(id, "ollama/steward/apply", { id }, "applied");
export const applyChange = (c: { key: string; field: string; to: unknown }, why: string) =>
  act(`${c.key}|${c.field}`, "ollama/steward/apply", { ...c, why }, "applied");
export const dismissFinding = (id: string) => act(id, "ollama/steward/dismiss", { id }, "dismissed for 24 hours");
export const undoLast = () => act("undo", "ollama/steward/undo", {}, "undone");
export const runNow = () => act("run", "ollama/steward/run", {}, "the steward ran once");

/** The exact env line on the clipboard (and on the button, for a page without one). */
export function copyHint(line: string): void {
  ollama.update(() => ({ copied: line }));
  void navigator.clipboard?.writeText(line).then(
    () => toast(`On the clipboard: ${line}`, "done"),
    () => toast(`Copy it by hand: ${line}`, "info", 6000),
  );
}

let live = false;

/** Once: a `steward` frame (the job in this process) reads the steward and the hosts again. */
export function startOllamaFeed(): void {
  if (live) return;
  live = true;
  let timer = 0;
  onEvent("steward", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(loadAll, 400);
  });
}

/** "by steward" / "by the hub" / "by you": who set a profile. */
export function byWho(by?: string): string {
  return by === "steward" ? "by steward" : by === "hub" ? "by the hub" : "by you";
}

export function gib(n: number | null | undefined): string {
  return typeof n === "number" ? `${(n / 2 ** 30).toFixed(1)} GiB` : "?";
}

export function k(n: number | null | undefined): string {
  if (typeof n !== "number") return "?";
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(Math.round(n));
}
