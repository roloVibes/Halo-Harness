// Local -> Hugging Face's store (3.3.5.0 R5; studio/local_hf_api.py, local_server_api.py): the model folders and what
// is on disk in each (GET local/hf/dirs, again when a download lands or a server starts or stops), the card open
// (Serve: the flags and their sources before Start; Delete: the uses card; Log: the tail; Download: the licence card
// first), and each action's answer, said on its own row. A download is a job in routes/local/jobs.ts.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";
import { takeJob } from "./jobs";
import { loadLibrary } from "./libstore";
import { loadHosts, loadModels } from "./store";
import type { DlPlan, HfDirs, HfModel, Licence, PullJob, ServePlan, Uses } from "./types";

export type DlAsk = { repo: string; file: string; dirs: string[]; dir: string; licence: Licence | null; plan: DlPlan | null; needsToken: boolean; cli: string };
type Open =
  | { act: "serve"; m: HfModel; plan: ServePlan | null; window: number | null; runtime: string; port: string; keep: boolean }
  | { act: "delete"; m: HfModel; uses: Uses | null; served: { id: string; port: number }[] }
  | { act: "log"; id: string; lines: string[] | null; path: string }
  | { act: "download"; ask: DlAsk };
type Said = { ok: boolean; text: string; cli?: string };
type Hf = { data: HfDirs | null; error: string; host: string; window: number | null; open: Open | null; busy: boolean; said: Record<string, Said> };

export const hf = createStore<Hf>({ data: null, error: "", host: "", window: null, open: null, busy: false, said: {} });

export function useHf<S>(select: (s: Hf) => S): S {
  return useStore(hf, select);
}

const enc = encodeURIComponent;
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const say = (k: string, s: Said) => hf.update((st) => ({ said: { ...st.said, [k]: s } }));

export async function loadDirs(): Promise<void> {
  const { host, window } = hf.get();
  try {
    const data = await api.get<HfDirs>("local/hf/dirs", { host, window: window || undefined });
    hf.update(() => ({ data, error: "" }));
  } catch (e) {
    hf.update(() => ({ error: msg(e) }));
  }
}

export function pick(patch: { host?: string; window?: number | null }): void {
  hf.update(() => patch);
  void loadDirs();
}

async function post(key: string, path: string, body: Record<string, unknown>): Promise<Record<string, unknown> | null> {
  hf.update(() => ({ busy: true }));
  try {
    const r = await api.post<Record<string, unknown>>(path, body);
    say(key, { ok: true, text: String(r.say || "done"), cli: String(r.cli || "") });
    return r;
  } catch (e) {
    const d = e instanceof ApiError ? e.data : {};
    say(key, { ok: false, text: msg(e), cli: String(d.cli || "") });
    return null;
  } finally {
    hf.update(() => ({ busy: false }));
  }
}

export async function addFolder(path: string): Promise<void> {
  if (await post("folder", "local/hf/dirs", { path })) void loadDirs();
}

export async function forgetFolder(path: string): Promise<void> {
  if (await post(`forget|${path}`, "local/hf/forget", { path })) void loadDirs();
}

export function close(): void {
  hf.update(() => ({ open: null }));
}

export async function openServe(m: HfModel, window: number | null = null, runtime = ""): Promise<void> {
  const before = hf.get().open;
  const keep = before && before.act === "serve" ? { port: before.port, keep: before.keep } : { port: "", keep: false };
  hf.update(() => ({ open: { act: "serve", m, plan: null, window, runtime, ...keep } }));
  try {
    const plan = await api.post<ServePlan>("local/hf/serve", { path: m.path, dry: true, window: window || undefined, runtime: runtime || undefined });
    const o = hf.get().open;
    if (o && o.act === "serve" && o.m.path === m.path) hf.update(() => ({ open: { ...o, plan } }));
  } catch (e) {
    say(`serve|${m.path}`, { ok: false, text: msg(e) });
  }
}

export function setServe(patch: { port?: string; keep?: boolean }): void {
  const o = hf.get().open;
  if (o && o.act === "serve") hf.update(() => ({ open: { ...o, ...patch } }));
}

export async function startServe(): Promise<void> {
  const o = hf.get().open;
  if (!o || o.act !== "serve") return;
  const port = parseInt(o.port, 10);
  const r = await post(`serve|${o.m.path}`, "local/hf/serve", { path: o.m.path, window: o.window || undefined, runtime: o.runtime || undefined,
    port: Number.isFinite(port) && port > 0 ? port : undefined, keep: o.keep });
  if (r) {
    void loadDirs();
    void loadHosts();
    void loadModels();
  }
}

export async function stopServer(id: string, key = `stop|${id}`): Promise<void> {
  if (await post(key, `local/server/${enc(id)}/stop`, {})) {
    void loadDirs();
    void loadHosts();
    void loadModels();
  }
}

export async function openLog(id: string): Promise<void> {
  hf.update(() => ({ open: { act: "log", id, lines: null, path: "" } }));
  try {
    const r = await api.get<{ lines: string[]; path: string }>(`local/server/${enc(id)}/log`, { n: 60 });
    hf.update(() => ({ open: { act: "log", id, lines: r.lines || [], path: r.path || "" } }));
  } catch (e) {
    hf.update(() => ({ open: { act: "log", id, lines: [msg(e)], path: "" } }));
  }
}

export async function openDelete(m: HfModel): Promise<void> {
  hf.update(() => ({ open: { act: "delete", m, uses: null, served: [] } }));
  try {
    const r = await api.get<{ uses: Uses; served: { id: string; port: number }[] }>("local/hf/uses", { path: m.path });
    hf.update(() => ({ open: { act: "delete", m, uses: r.uses, served: r.served || [] } }));
  } catch (e) {
    say(`delete|${m.path}`, { ok: false, text: msg(e) });
  }
}

export async function deleteModel(m: HfModel, force: boolean): Promise<void> {
  if (await post(`delete|${m.path}`, "local/hf/delete", { path: m.path, force })) {
    void loadDirs();
    void loadLibrary();
  }
}

/** A Library hub row's Download: the licence card first (POST without accept answers 422 with the licence line). */
export async function askDownload(repo: string, file: string, dirs: string[], dir = ""): Promise<void> {
  const ask: DlAsk = { repo, file, dirs, dir: dir || dirs[0] || "", licence: null, plan: null, needsToken: false, cli: "" };
  hf.update(() => ({ open: { act: "download", ask } }));
  try {
    await api.post("local/hf/download", { repo, file, dir: ask.dir || undefined });
  } catch (e) {
    const d = (e instanceof ApiError ? e.data : {}) as Record<string, unknown>;
    const next = { ...ask, licence: (d.licence as Licence) || null, plan: (d.plan as DlPlan) || null, needsToken: !!d.needs_token, cli: String(d.cli || "") };
    hf.update(() => ({ open: { act: "download", ask: next } }));
    if (!d.licence) say(`dl|${repo}|${file}`, { ok: false, text: msg(e), cli: String(d.cli || "") });
  }
}

export async function acceptDownload(): Promise<void> {
  const o = hf.get().open;
  if (!o || o.act !== "download") return;
  const { repo, file, dir } = o.ask;
  const r = await post(`dl|${repo}|${file}`, "local/hf/download", { repo, file, dir: dir || undefined, accept: true });
  if (r) {
    takeJob(r as unknown as PullJob);
    close();
  }
}

export function setDlDir(dir: string): void {
  const o = hf.get().open;
  if (o && o.act === "download") void askDownload(o.ask.repo, o.ask.file, o.ask.dirs, dir);
}
