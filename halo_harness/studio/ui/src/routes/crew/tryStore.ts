// Try it (3.6.0.0 R1): one real run of the agent in the form, as it stands (saved or not), on a throwaway copy of the
// project (crew/trial.py). Its cost on the picked model is asked for BEFORE the run (GET crew/estimate); the run's
// progress comes on the feed (`crew` frames) and by a read each second while it runs; Stop ends it. The result shows
// in the tab; once it is drawn while the page is in view, it is marked seen (POST crew/try/<id>/seen), else it waits
// as an Attention row (live/crew_attention.py) until it is.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { createStore, toast, useStore } from "../../lib/store";
import { crew } from "./store";
import type { TryRec } from "./types";

export type TryState = { text: string; rec: TryRec | null; estimate: { usd: number | null; line: string } | null; estFor: string; busy: boolean };
export const tries = createStore<TryState>({ text: "", rec: null, estimate: null, estFor: "", busy: false });
export const useTry = <T,>(pick: (s: TryState) => T): T => useStore(tries, pick);

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
let timer = 0;
const running = (r: TryRec | null) => !!r && (r.state === "running" || r.state === "stopping");

export async function estimateFor(model: string): Promise<void> {
  if (tries.get().estFor === model && tries.get().estimate) return;
  tries.update(() => ({ estFor: model }));
  try {
    const got = await api.get<{ usd: number | null; line: string }>("crew/estimate", { model });
    if (tries.get().estFor === model) tries.update(() => ({ estimate: got }));
  } catch (e) {
    tries.update(() => ({ estimate: { usd: null, line: msg(e) } }));
  }
}

function poll(): void {
  window.clearTimeout(timer);
  const r = tries.get().rec;
  if (!running(r)) return;
  timer = window.setTimeout(async () => {
    try {
      const got = await api.get<{ try: TryRec }>(`crew/try/${r!.id}`);
      if (tries.get().rec?.id === got.try.id) tries.update(() => ({ rec: got.try }));
    } catch {
      /* the next read tries again */
    }
    poll();
  }, 1000);
}

export async function startTry(): Promise<void> {
  const s = tries.get();
  const form = crew.get().form;
  if (!form || !s.text.trim() || running(s.rec)) return;
  tries.update(() => ({ busy: true }));
  try {
    const got = await api.post<{ try: TryRec }>("crew/try", { kind: "agent", body: form, request: s.text.trim() });
    tries.update(() => ({ rec: got.try, busy: false }));
    poll();
  } catch (e) {
    tries.update(() => ({ busy: false }));
    toast(msg(e), "error", 6000);
  }
}

export async function stopTry(): Promise<void> {
  const r = tries.get().rec;
  if (!running(r)) return;
  try {
    await api.post(`crew/try/${r!.id}/stop`);
    tries.update((s) => (s.rec ? { rec: { ...s.rec, state: "stopping" } } : {}));
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export async function markSeen(id: string): Promise<void> {
  try {
    await api.post(`crew/try/${id}/seen`);
    tries.update((s) => (s.rec?.id === id ? { rec: { ...s.rec, seen: true } } : {}));
  } catch {
    /* it stays an Attention row until it is seen */
  }
}

/** A run named by an Attention row's open: show it (with its agent) in the tab. */
export async function showTry(id: string): Promise<void> {
  try {
    const got = await api.get<{ try: TryRec }>(`crew/try/${id}`);
    tries.update(() => ({ rec: got.try, text: got.try.request }));
    poll();
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export const setTryText = (text: string) => tries.update(() => ({ text }));
export const clearTry = () => tries.update(() => ({ rec: null }));

let wired = false;
export function wireTryFeed(): void {
  if (wired) return;
  wired = true;
  onEvent("crew", (f) => {
    const got = (f.data as { try?: TryRec } | null)?.try;
    if (got && tries.get().rec?.id === got.id) tries.update(() => ({ rec: got }));
  });
}
