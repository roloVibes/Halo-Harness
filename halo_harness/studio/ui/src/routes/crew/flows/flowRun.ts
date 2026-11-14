// Try it for a workflow (3.6.0.0 R2): one real run of every step of the workflow as the form holds it (saved or not),
// on a throwaway copy of the project (crew/trial_flow.py). Its cost band is in the record before the first call; each
// step's result, the agents that ran, their time and cost arrive on the feed (`crew` frames) and by a read each second
// while it runs; Stop ends it. Drawn while the page is in view, it is marked seen; else it waits as an Attention row.
import { api, ApiError } from "../../../lib/api";
import { onEvent } from "../../../lib/events";
import { createStore, toast, useStore } from "../../../lib/store";
import type { TryRec } from "../types";
import { flows } from "./flowStore";

export type FlowTryState = { text: string; rec: TryRec | null; busy: boolean };
export const flowTries = createStore<FlowTryState>({ text: "", rec: null, busy: false });
export const useFlowTry = <T,>(pick: (s: FlowTryState) => T): T => useStore(flowTries, pick);

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
export const running = (r: TryRec | null) => !!r && (r.state === "running" || r.state === "stopping");
let timer = 0;

function poll(): void {
  window.clearTimeout(timer);
  const r = flowTries.get().rec;
  if (!running(r)) return;
  timer = window.setTimeout(async () => {
    try {
      const got = await api.get<{ try: TryRec }>(`crew/try/${r!.id}`);
      if (flowTries.get().rec?.id === got.try.id) flowTries.update(() => ({ rec: got.try }));
    } catch {
      /* the next read tries again */
    }
    poll();
  }, 1000);
}

export async function startFlowTry(): Promise<void> {
  const s = flowTries.get();
  const form = flows.get().form;
  if (!form || !s.text.trim() || running(s.rec)) return;
  flowTries.update(() => ({ busy: true }));
  try {
    const got = await api.post<{ try: TryRec }>("crew/try", { kind: "workflow", body: form, request: s.text.trim() });
    flowTries.update(() => ({ rec: got.try, busy: false }));
    poll();
  } catch (e) {
    flowTries.update(() => ({ busy: false }));
    toast(msg(e), "error", 6000);
  }
}

export async function stopFlowTry(): Promise<void> {
  const r = flowTries.get().rec;
  if (!running(r)) return;
  try {
    await api.post(`crew/try/${r!.id}/stop`);
    flowTries.update((s) => (s.rec ? { rec: { ...s.rec, state: "stopping" } } : {}));
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export async function markFlowSeen(id: string): Promise<void> {
  try {
    await api.post(`crew/try/${id}/seen`);
    flowTries.update((s) => (s.rec?.id === id ? { rec: { ...s.rec, seen: true } } : {}));
  } catch {
    /* it stays an Attention row until it is seen */
  }
}

/** A run named by an Attention row's open, or one the builder started: show it in the tab. */
export async function showFlowTry(id: string): Promise<void> {
  try {
    const got = await api.get<{ try: TryRec }>(`crew/try/${id}`);
    flowTries.update(() => ({ rec: got.try, text: got.try.request }));
    poll();
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export const setFlowTryText = (text: string) => flowTries.update(() => ({ text }));

let wired = false;
export function wireFlowTryFeed(): void {
  if (wired) return;
  wired = true;
  onEvent("crew", (f) => {
    const got = (f.data as { try?: TryRec } | null)?.try;
    if (got && got.kind === "workflow" && flowTries.get().rec?.id === got.id) flowTries.update(() => ({ rec: got }));
  });
}
