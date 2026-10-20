// The coach's store (3.0.9.0 R3): one result per run (`<kind>:<run>`), read
// once from the run kind's route and kept; the cards a viewer dismissed, per
// run, in localStorage (`halo.coach.dismissed.<kind>.<run>`), so a dismissed
// card stays hidden after a reload. Nothing here writes a run file; the
// loop's POSTs (ask, apply, undo: lib/coach/actions.ts) keep their busy word
// per card in `busy` and the open confirm card per card in `confirm`; the
// Probe button (3.1.6.0 R2, lib/coach/probe.ts) keeps its state per run in `probe`.
import { api, ApiError } from "../api";
import { createStore, useStore } from "../store";
import type { CoachPreview, CoachResult, CoachRunKind, ProbeEstimate } from "./types";

export type CoachEntry = { loading: boolean; error: string; result: CoachResult | null };
/** 3.1.6.0 R2: the Probe button's state per run: the cost line once asked, the confirm open, the latest step line. */
export type ProbeUi = { estimate?: ProbeEstimate; open?: boolean; busy?: string; line?: string; error?: string };
export type CoachState = {
  runs: Record<string, CoachEntry>;
  dismissed: Record<string, string[]>;
  busy: Record<string, string>;
  confirm: Record<string, CoachPreview>;
  probe: Record<string, ProbeUi>;
};

export const coach = createStore<CoachState>({ runs: {}, dismissed: {}, busy: {}, confirm: {}, probe: {} });

export function useCoach<S>(select: (s: CoachState) => S): S {
  return useStore(coach, select);
}

export const keyOf = (kind: CoachRunKind, run: string) => `${kind}:${run}`;
const storageKey = (kind: CoachRunKind, run: string) => `halo.coach.dismissed.${kind}.${run}`;

export function routeOf(kind: CoachRunKind, run: string): string {
  const r = encodeURIComponent(run);
  if (kind === "orchestra") return `orchestra/${r}/coach`;
  if (kind === "mission") return `fleet/missions/${r}/coach`;
  return "team/coach";
}

function readDismissed(kind: CoachRunKind, run: string): string[] {
  try {
    const raw = JSON.parse(localStorage.getItem(storageKey(kind, run)) || "[]");
    return Array.isArray(raw) ? raw.map(String) : [];
  } catch {
    return [];
  }
}

function writeDismissed(kind: CoachRunKind, run: string, ids: string[]): void {
  try {
    if (ids.length) localStorage.setItem(storageKey(kind, run), JSON.stringify(ids));
    else localStorage.removeItem(storageKey(kind, run));
  } catch {
    /* a private window: the card comes back on a reload */
  }
}

/** Read the coach for one run (once; `again` reads it again). */
export async function loadCoach(kind: CoachRunKind, run: string, again = false): Promise<void> {
  if (!run) return;
  const key = keyOf(kind, run);
  const cur = coach.get().runs[key];
  if (cur && !again && (cur.loading || cur.result)) return;
  coach.update((s) => ({
    runs: { ...s.runs, [key]: { loading: true, error: "", result: cur?.result || null } },
    dismissed: { ...s.dismissed, [key]: readDismissed(kind, run) },
  }));
  try {
    const result = await api.get<CoachResult>(routeOf(kind, run), kind === "team" ? { run } : undefined);
    coach.update((s) => ({ runs: { ...s.runs, [key]: { loading: false, error: "", result } } }));
  } catch (e) {
    const error = e instanceof ApiError ? e.message : String(e);
    coach.update((s) => ({ runs: { ...s.runs, [key]: { loading: false, error, result: null } } }));
  }
}

export function dismiss(kind: CoachRunKind, run: string, id: string): void {
  const key = keyOf(kind, run);
  const next = [...new Set([...(coach.get().dismissed[key] || readDismissed(kind, run)), id])];
  writeDismissed(kind, run, next);
  coach.update((s) => ({ dismissed: { ...s.dismissed, [key]: next } }));
}

export function restoreAll(kind: CoachRunKind, run: string): void {
  writeDismissed(kind, run, []);
  coach.update((s) => ({ dismissed: { ...s.dismissed, [keyOf(kind, run)]: [] } }));
}
