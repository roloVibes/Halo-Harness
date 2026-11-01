// Local -> Pool's store (3.3.8.0 R1; studio/pool_api.py): the members with their GPU, free / total VRAM, link, RTT
// and share of the split (GET local/pool/members), the recommendation (GET local/pool/recommend, ?batch=1 shows the
// batch-only models), and the last scan (POST local/pool/scan: a button, never a page load). The ostore pattern
// (routes/fleet/ostore.ts): the page reads both on open and again every REFRESH_MS while it is open; a write (add,
// remove, scan) reads them again at once. Each action's answer is said on its own row (`said`).
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";

export const REFRESH_MS = 30_000;

export type Link = { type: "wired" | "wireless" | "unknown"; speed_mbps: number | null };
export type Member = {
  name: string; host: string; rpc_port: number; kind: "paired" | "local" | "address"; addr: string; gpu: string;
  total_gb: number | null; usable_gb: number | null; resident_gb: number; resident: string[]; helper_gb: number;
  claims_gb: number; free_gb: number | null; vram_source: "card" | "stated" | "unknown"; source: string; link: Link;
  link_word: string; line: string; share: number | null; share_word: string; rtt_ms: number | null; rtt_alive: boolean | null; rtt_word: string;
};
export type Members = {
  members: Member[]; split: number[]; split_from: string; free_gb: number; total_gb: number; head: string; problems: string[];
  file: string; rpc_port: number; scan: { at: number | null; line: string }; cli: string;
};
export type Download = { repo: string; file: string; gb: number; eta_s: number; eta: string; eta_from: string; cli: string };
export type Verdict = {
  model: string; display: string; state: "single" | "pool" | "no"; node: string | null; split: number[]; split_from: string;
  max_ctx_f16: number; max_ctx_q8: number; need_gb: number | null; free_gb: number | null; nodes: number; lines: string[];
  verdict: string; badge: string; batch_only: boolean; min_build: number | null; active_b: number; weights_gb: number;
  routing_table_gb: number; rank: number | null; tags: string[]; preview: string; download: Download | null; speed_word: string;
  repo: string;
};
export type Rec = { rows: Verdict[]; others: Verdict[]; hidden: { model: string; line: string }[]; head: string; nodes: number;
  free_gb: number; allow_batch: boolean; cli: string };
export type Probe = { host: string; port: number; alive: boolean; rtt_ms: number | null; error: string; wifi_suspect: boolean;
  line: string; name?: string | null; member?: string | null; paired?: string | null };
export type Scan = { at: number; port: number; networks: string[]; candidates: Probe[]; members: (Probe & { name: string })[];
  notes: string[]; line: string; cli: string };
type Said = { ok: boolean; text: string };
type PoolState = { members: Members | null; rec: Rec | null; scan: Scan | null; batch: boolean; error: string; busy: string;
  said: Record<string, Said> };

export const pool = createStore<PoolState>({ members: null, rec: null, scan: null, batch: false, error: "", busy: "", said: {} });

export function usePool<S>(select: (s: PoolState) => S): S {
  return useStore(pool, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const say = (k: string, s: Said) => pool.update((st) => ({ said: { ...st.said, [k]: s } }));

export async function loadMembers(): Promise<void> {
  try {
    const members = await api.get<Members>("local/pool/members");
    pool.update(() => ({ members, error: "" }));
  } catch (e) {
    pool.update(() => ({ error: msg(e) }));
  }
}

export async function loadRec(): Promise<void> {
  try {
    const rec = await api.get<Rec>("local/pool/recommend", pool.get().batch ? { batch: 1 } : undefined);
    pool.update(() => ({ rec, error: "" }));
  } catch (e) {
    pool.update(() => ({ error: msg(e) }));
  }
}

export function loadPool(): void {
  void loadMembers();
  void loadRec();
}

export function setBatch(on: boolean): void {
  pool.update(() => ({ batch: on }));
  void loadRec();
}

/** Scan: the RPC port on this machine's /24 and on every member -- only when the button is pressed. */
export async function scanNow(): Promise<void> {
  pool.update(() => ({ busy: "scan" }));
  try {
    const scan = await api.post<Scan>("local/pool/scan", {});
    pool.update(() => ({ scan }));
    say("scan", { ok: true, text: scan.line });
    loadPool();
  } catch (e) {
    say("scan", { ok: false, text: msg(e) });
  } finally {
    pool.update(() => ({ busy: "" }));
  }
}

async function edit(key: string, body: Record<string, unknown>): Promise<void> {
  pool.update(() => ({ busy: key }));
  try {
    const r = await api.post<{ lines: string[] }>("local/pool/members", body);
    say(key, { ok: true, text: (r.lines || []).join("; ") });
    loadPool();
  } catch (e) {
    say(key, { ok: false, text: msg(e) });
  } finally {
    pool.update(() => ({ busy: "" }));
  }
}

export const addMember = (name: string, host: string, port: number) => edit(`add|${host}:${port}`, { op: "add", name, host, port });
export const removeMember = (name: string) => edit(`rm|${name}`, { op: "remove", name });

/** A scan candidate's member name: its paired host's name (unless that host is a member already), its reverse-DNS
 *  name, else "worker-<last octet>". */
export function nameFor(c: Probe, paired = true): string {
  return (paired && c.paired) || c.name || `worker-${c.host.split(/[.:]/).filter(Boolean).pop() || "1"}`;
}

export function gb(n: number | null | undefined): string {
  return typeof n === "number" ? `${n.toFixed(1)} GB` : "?";
}
