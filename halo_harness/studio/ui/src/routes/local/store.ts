// The Local section's store (3.3.5.0 R1; studio/local_api.py): the hosts (GET local/hosts), the models (GET
// local/models), the live samples (GET local/resources for the last 5 minutes, then every `resources` frame), the
// traffic (GET local/traffic?since=15m, then every `traffic` frame, deduped by the line's id), and the answer of
// each action, said on its own row (no toast). The Resources page holds the sampler on through `watch`: a lease of
// 45 s the page renews every 15 s while it is shown (POST local/resources/watch {on}).
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { onFilesChanged } from "../../lib/filesLive";
import { createStore, useStore } from "../../lib/store";
import type { Bucket, HostCard, ModelsAnswer, Said, Sample, Traffic, TRow } from "./types";

export const KEEP_S = 300;
export const RENEW_MS = 15_000;
const MAX_ROWS = 600;

type LocalState = {
  hosts: HostCard[] | null; models: ModelsAnswer | null; samples: Record<string, Sample[]>; rows: TRow[];
  spark: Record<string, Bucket[]>; sinceS: number; error: string; busy: string; said: Record<string, Said>;
};

export const local = createStore<LocalState>({ hosts: null, models: null, samples: {}, rows: [], spark: {}, sinceS: 900, error: "", busy: "", said: {} });

export function useLocal<S>(select: (s: LocalState) => S): S {
  return useStore(local, select);
}

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

export async function loadHosts(): Promise<void> {
  try {
    const r = await api.get<{ hosts: HostCard[] }>("local/hosts");
    local.update(() => ({ hosts: r.hosts || [], error: "" }));
  } catch (e) {
    local.update(() => ({ error: msg(e) }));
  }
}

export async function loadModels(): Promise<void> {
  try {
    const models = await api.get<ModelsAnswer>("local/models");
    local.update(() => ({ models, error: "" }));
  } catch (e) {
    local.update(() => ({ error: msg(e) }));
  }
}

function addSample(s: Sample): void {
  local.update((st) => {
    const list = [...(st.samples[s.host] || []).filter((x) => x.t !== s.t), s].filter((x) => x.t >= s.t - KEEP_S);
    return { samples: { ...st.samples, [s.host]: list } };
  });
}

export async function loadResources(): Promise<void> {
  try {
    const r = await api.get<{ samples: Sample[] }>("local/resources");
    const by: Record<string, Sample[]> = {};
    for (const s of r.samples || []) (by[s.host] = by[s.host] || []).push(s);
    local.update((st) => ({ samples: { ...by, ...Object.fromEntries(Object.entries(st.samples).filter(([h]) => !by[h])) } }));
  } catch {
    /* the strip waits for the first frame */
  }
}

export async function watch(on: boolean): Promise<void> {
  try {
    await api.post("local/resources/watch", { on });
  } catch {
    /* the strip keeps the samples it has */
  }
}

function bump(spark: Record<string, Bucket[]>, r: TRow): Record<string, Bucket[]> {
  if (r.type !== "call" || r.t == null || r.kind === "calibrate") return spark;
  const t = Math.floor(r.t / 60) * 60;
  const list = [...(spark[r.host] || [])];
  let b = list.find((x) => x.t === t);
  if (!b) {
    b = { t, calls: 0, trims: 0, cuts: 0, errors: 0, bytes_in: 0, bytes_out: 0 };
    list.push(b);
    list.sort((a, c) => a.t - c.t);
  }
  const nb = { ...b, calls: b.calls + 1, trims: b.trims + (r.trimmed ? 1 : 0), cuts: b.cuts + (r.cut ? 1 : 0),
               errors: b.errors + (r.ok ? 0 : 1), bytes_in: b.bytes_in + (r.bytes_in || 0), bytes_out: b.bytes_out + (r.bytes_out || 0) };
  return { ...spark, [r.host]: list.map((x) => (x.t === t ? nb : x)).slice(-60) };
}

export function addRows(rows: TRow[]): void {
  local.update((st) => {
    const have = new Set(st.rows.map((r) => r.id));
    const fresh = rows.filter((r) => r && r.id && !have.has(r.id));
    if (!fresh.length) return {};
    let spark = st.spark;
    for (const r of fresh) spark = bump(spark, r);
    const merged = [...st.rows, ...fresh].sort((a, b) => (a.t || 0) - (b.t || 0)).slice(-MAX_ROWS);
    return { rows: merged, spark };
  });
}

export async function loadTraffic(): Promise<void> {
  try {
    const r = await api.get<Traffic>("local/traffic", { since: "15m" });
    const rows = [...(r.rows || []), ...(r.events || [])].sort((a, b) => (a.t || 0) - (b.t || 0));
    local.update(() => ({ rows: rows.slice(-MAX_ROWS), spark: r.spark || {}, sinceS: r.since_s || 900 }));
  } catch (e) {
    local.update(() => ({ error: msg(e) }));
  }
}

let live = false;

/** Once: the live feed's `resources` and `traffic` frames, and the hosts again when config.json moves. */
export function startLocal(): void {
  if (live) return;
  live = true;
  onEvent("resources", (f) => {
    const s = f.data as Sample | undefined;
    if (s && s.host && typeof s.t === "number") addSample(s);
  });
  onEvent("traffic", (f) => {
    const d = f.data as { rows?: TRow[] } | undefined;
    if (d?.rows?.length) addRows(d.rows);
  });
  onFilesChanged("config", () => {
    void loadHosts();
  });
}

function say(key: string, s: Said | null): void {
  local.update((st) => {
    const said = { ...st.said };
    if (s) said[key] = s;
    else delete said[key];
    return { said };
  });
}

async function act(key: string, path: string, body: Record<string, unknown>): Promise<Record<string, unknown> | null> {
  local.update(() => ({ busy: key }));
  try {
    const r = await api.post<Record<string, unknown>>(path, body);
    const lines = Array.isArray(r.lines) ? (r.lines as string[]).join(" · ") : "";
    say(key, { ok: true, text: String(r.say || lines || "done") });
    return r;
  } catch (e) {
    say(key, { ok: false, text: msg(e) });
    return null;
  } finally {
    local.update(() => ({ busy: "" }));
  }
}

export async function loadModel(host: string, model: string, keepAlive?: string): Promise<void> {
  const body: Record<string, unknown> = { model };
  if (keepAlive) body.keep_alive = keepAlive;
  if (await act(`${host}|${model}`, `local/host/${encodeURIComponent(host)}/load`, body)) void loadHosts();
}

export async function unloadModel(host: string, model: string): Promise<void> {
  if (await act(`${host}|${model}`, `local/host/${encodeURIComponent(host)}/unload`, { model })) void loadHosts();
}

export async function addHost(url: string, name: string): Promise<void> {
  if (await act(`add|${url}`, "local/host/add", { url, name })) void loadHosts();
}

/** Idea 4, "make it fit": the planner's chosen option applied (each change through steward/apply), Undo beside it. */
export async function makeItFit(h: HostCard): Promise<void> {
  const c = h.plan?.chosen;
  if (!c || !c.changes.length) return;
  let n = 0;
  for (const ch of c.changes) if (await act(`fit|${h.name}`, "ollama/steward/apply", { ...ch, why: `make it fit: ${c.says}` })) n += 1;
  if (n) say(`fit|${h.name}`, { ok: true, text: `applied: ${c.says}`, undo: n });
  void loadHosts();
}

export async function undoFit(h: HostCard, n: number): Promise<void> {
  for (let i = 0; i < n; i += 1) await act(`fit|${h.name}`, "ollama/steward/undo", {});
  void loadHosts();
}

export async function useAsDefault(ref: string): Promise<void> {
  await act(`default|${ref}`, "setup/config", { key: "model", value: ref });
}

export async function coderLane(ref: string): Promise<void> {
  await act(`lane|${ref}`, "models/lane", { ref });
}

export function gib(n: number | null | undefined): string {
  return typeof n === "number" ? `${(n / 2 ** 30).toFixed(1)} GiB` : "?";
}

export function kb(n: number | null | undefined): string {
  if (typeof n !== "number") return "?";
  return n >= 2 ** 20 ? `${(n / 2 ** 20).toFixed(1)} MB` : n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`;
}
