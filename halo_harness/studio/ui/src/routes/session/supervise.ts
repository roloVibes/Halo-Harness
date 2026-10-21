// The supervisor's morning line (3.1.8.0 R1): GET /api/supervise/summary gives
// "N goals done, M waiting on you, $X" when `halo supervise`'s pulse is live.
// The Session landing shows it (Start.tsx); it refreshes on the Session section's
// own cadence. Nothing shows when no supervisor runs.
import { call } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";

export type SuperviseSummary = {
  running: boolean;
  state: string;
  goals: { queued?: number; running?: number; done?: number; parked?: number };
  done: number;
  waiting: number;
  cost_usd: number;
  line: string;
};

const EMPTY: SuperviseSummary = { running: false, state: "off", goals: {}, done: 0, waiting: 0, cost_usd: 0, line: "" };

export const supervise = createStore<SuperviseSummary>(EMPTY);

export function useSupervise<S>(select: (s: SuperviseSummary) => S): S {
  return useStore(supervise, select);
}

let timer: ReturnType<typeof setInterval> | null = null;

export async function loadSupervise(): Promise<void> {
  try {
    const data = await call<SuperviseSummary>("GET", "supervise/summary");
    supervise.update(() => ({ ...EMPTY, ...data }));
  } catch {
    supervise.update(() => EMPTY);
  }
}

/** Poll the summary while the Session section shows; stop when it leaves. */
export function watchSupervise(on: boolean): void {
  if (on && timer === null) {
    void loadSupervise();
    timer = setInterval(() => void loadSupervise(), 15000);
  } else if (!on && timer !== null) {
    clearInterval(timer);
    timer = null;
  }
}
