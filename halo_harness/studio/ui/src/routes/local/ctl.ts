// Local -> Models' actions on an installed model (3.3.5.0 R3; studio/local_control_api.py): the card a row's
// actions menu opens (Show, the tuned twin, Copy / Rename, Delete with its uses card), what each card read, and the
// calls. Every call answers with `cli`, the `halo models` line that does the same; each card shows it.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";
import { loadHosts, loadModels } from "./store";
import type { ModelEntry, ShowAnswer, TwinPlan, Uses } from "./types";

export type Act = "show" | "twin" | "copy" | "rename" | "delete" | "retire";
type Ctl = {
  open: { act: Act; host: string; m: ModelEntry } | null;
  show: ShowAnswer | null; plan: TwinPlan | null; uses: Uses | null;
  busy: boolean; said: { ok: boolean; text: string; cli?: string } | null;
};
export const ctl = createStore<Ctl>({ open: null, show: null, plan: null, uses: null, busy: false, said: null });

export function useCtl<S>(select: (s: Ctl) => S): S {
  return useStore(ctl, select);
}

const enc = encodeURIComponent;
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
export const line = (verb: string, host: string, ...words: string[]) => ["halo models", verb, ...words.filter(Boolean), "--host", host].join(" ");

export function openAct(act: Act, host: string, m: ModelEntry): void {
  ctl.update(() => ({ open: { act, host, m }, show: null, plan: null, uses: null, said: null, busy: false }));
  if (act === "show") void readShow(host, m.model);
  if (act === "delete" || act === "retire") void readUses(host, m.model);
}

export function closeAct(): void {
  ctl.update(() => ({ open: null, show: null, plan: null, uses: null, said: null, busy: false }));
}

async function readShow(host: string, model: string): Promise<void> {
  try {
    const show = await api.get<ShowAnswer>(`local/host/${enc(host)}/show`, { model });
    ctl.update(() => ({ show }));
  } catch (e) {
    ctl.update(() => ({ said: { ok: false, text: msg(e) } }));
  }
}

async function readUses(host: string, model: string): Promise<void> {
  try {
    const r = await api.get<{ uses: Uses }>(`local/host/${enc(host)}/uses`, { model });
    ctl.update(() => ({ uses: r.uses }));
  } catch (e) {
    ctl.update(() => ({ said: { ok: false, text: msg(e) } }));
  }
}

async function run(path: string, body: Record<string, unknown>, after = true): Promise<Record<string, unknown> | null> {
  ctl.update(() => ({ busy: true, said: null }));
  try {
    const r = await api.post<Record<string, unknown>>(path, body);
    ctl.update(() => ({ busy: false, said: { ok: true, text: String(r.say || "done"), cli: String(r.cli || "") } }));
    if (after) {
      void loadModels();
      void loadHosts();
    }
    return r;
  } catch (e) {
    const d = e instanceof ApiError ? e.data : {};
    ctl.update(() => ({ busy: false, said: { ok: false, text: msg(e), cli: String(d.cli || "") }, uses: (d.uses as Uses) || ctl.get().uses }));
    return null;
  }
}

export async function planTwin(host: string, model: string, window: number): Promise<void> {
  ctl.update(() => ({ plan: null }));
  const r = await run(`local/host/${enc(host)}/twin`, { name: model, window, dry: true }, false);
  if (r) ctl.update(() => ({ plan: r as unknown as TwinPlan, said: null }));
}

export async function makeTwin(host: string, model: string, window: number): Promise<void> {
  await run(`local/host/${enc(host)}/twin`, { name: model, window });
}

export async function copyModel(host: string, src: string, dst: string, rename: boolean): Promise<void> {
  await run(`local/host/${enc(host)}/${rename ? "rename" : "copy"}`, { src, dst });
}

export async function deleteModel(host: string, model: string, force: boolean): Promise<void> {
  const r = await run(`local/host/${enc(host)}/delete`, { name: model, force });
  if (r) ctl.update(() => ({ uses: null }));
}

/** 3.3.6.0 R4: Retire (studio/local_shelf_api.py): the delete with a shelf line, so a re-pull is one click. */
export async function retireModel(host: string, model: string, why: string, force: boolean): Promise<void> {
  const r = await run(`local/host/${enc(host)}/retire`, { name: model, why, force });
  if (r) ctl.update(() => ({ uses: null }));
}
