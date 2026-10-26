// The Check block's store (3.3.0.0 R3): which checks are ticked (the
// state's `default_on` until one is changed), the gym's models, whether the
// guided first run's card was shown (its box can be ticked only then), and
// the running job: `POST setup/check` starts it, each check's frames arrive
// as `setup` frames on the live feed (studio/setup_check_job.py) and are
// polled from `GET setup/check` too, so a reloaded page or a closed feed
// still catches up. The summary frame re-reads the state (the strip's
// "Last check").
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { noProviderJump } from "../../lib/start";
import { createStore, toast, useStore } from "../../lib/store";
import { loadSetup, setup, type CheckResult, type LastCheck, type SetupData } from "./store";

export type CheckFrame = { key: string; title: string; state: string; lines: string[] };
export type CheckSummary = { ok: boolean; stopped: boolean; results: CheckResult[] };
type Job = { job: string; running: boolean; keys: string[]; checks: CheckFrame[]; summary: CheckSummary | null };

type CheckState = {
  ticks: Record<string, boolean>;
  models: Record<string, boolean>;
  cardShown: boolean;
  job: string;
  keys: string[];
  frames: Record<string, CheckFrame>;
  summary: CheckSummary | null;
  running: boolean;
  busy: boolean;
  error: string;
};

export const check = createStore<CheckState>({ ticks: {}, models: {}, cardShown: false, job: "", keys: [], frames: {}, summary: null,
  running: false, busy: false, error: "" });

export function useCheck<S>(select: (s: CheckState) => S): S {
  return useStore(check, select);
}

/** Is check `key` ticked: the user's tick, else its default (the guided first run only once its card was shown). */
export function ticked(s: CheckState, d: SetupData | null, key: string): boolean {
  if (key === "start" && !s.cardShown) return false;
  if (key in s.ticks) return s.ticks[key];
  return !!d?.checks.find((c) => c.key === key)?.default_on;
}

/** Is the gym model `ref` ticked (every offered model is, until unticked). */
export const modelTicked = (s: CheckState, ref: string) => s.models[ref] !== false;

export function tick(key: string, on: boolean): void {
  check.update((s) => ({ ticks: { ...s.ticks, [key]: on } }));
}

export function tickModel(ref: string, on: boolean): void {
  check.update((s) => ({ models: { ...s.models, [ref]: on } }));
}

export function showCard(): void {
  check.update(() => ({ cardShown: true }));
}

function adopt(job: Job | null): void {
  if (!job) return;
  const frames: Record<string, CheckFrame> = {};
  for (const f of job.checks || []) frames[f.key] = f;
  check.update(() => ({ job: job.job, keys: job.keys || [], frames, summary: job.summary, running: job.running }));
}

let fed = false;
let timer = 0;

function feed(): void {
  if (fed) return;
  fed = true;
  onEvent("setup", (f) => {
    const d = (f.data || {}) as Record<string, unknown>;
    if (d.job && check.get().job && d.job !== check.get().job) return; // another job's late frame
    if (d.key === "summary") {
      check.update(() => ({ summary: d as unknown as CheckSummary, running: false }));
      void loadSetup(); // the strip's Last check
      return;
    }
    if (typeof d.key === "string") {
      const frame = d as unknown as CheckFrame;
      check.update((s) => ({ job: String(d.job || s.job), frames: { ...s.frames, [frame.key]: frame }, running: !s.summary }));
    }
  });
}

function poll(): void {
  window.clearTimeout(timer);
  timer = window.setTimeout(async () => {
    try {
      adopt((await api.get<{ job: Job | null }>("setup/check")).job);
    } catch {
      /* the next poll tries again */
    }
    if (check.get().running) poll();
    else void loadSetup();
  }, 1500);
}

/** On the block's first draw: the live feed, and the job a reloaded page missed. */
export async function startCheck(): Promise<void> {
  feed();
  try {
    const r = await api.get<{ job: Job | null }>("setup/check");
    adopt(r.job);
    if (r.job?.running) poll();
  } catch {
    /* an older Studio: nothing to catch up */
  }
}

/** Run the ticked checks (in the list's order) as one job; the gym runs on its ticked models. */
export async function runChecks(): Promise<void> {
  const s = check.get();
  const d = setup.get().data;
  const keys = (d?.checks || []).map((c) => c.key).filter((k) => ticked(s, d, k));
  const models = (d?.gym_models || []).map((m) => m.ref).filter((r) => modelTicked(s, r));
  check.update(() => ({ busy: true, error: "", frames: {}, summary: null }));
  try {
    const r = await api.post<{ job: Job }>("setup/check", { checks: keys, ...(keys.includes("gym") ? { models } : {}) });
    adopt(r.job);
    check.update(() => ({ running: true }));
    poll();
  } catch (e) {
    if (e instanceof ApiError && e.status === 422 && e.data.reason === "no_provider") {
      noProviderJump();
      check.update(() => ({ error: e.message }));
    } else {
      const text = e instanceof ApiError && e.problems.length ? e.problems.join("; ") : e instanceof Error ? e.message : String(e);
      check.update(() => ({ error: text }));
      toast(text, "error", 6000);
    }
  } finally {
    check.update(() => ({ busy: false }));
  }
}

export async function stopChecks(): Promise<void> {
  try {
    await api.post("setup/check/stop");
  } catch {
    /* the poll shows what happened */
  }
}

/** The strip's Last check: "ok 12:04", "2 failed 12:04", "stopped 12:04" or "not run". */
export function lastCheckWord(last: LastCheck | null | undefined): string {
  if (!last || !last.when) return "not run";
  const at = new Date(last.when * 1000);
  const hhmm = `${String(at.getHours()).padStart(2, "0")}:${String(at.getMinutes()).padStart(2, "0")}`;
  const failed = (last.results || []).filter((r) => !r.ok).length;
  if (failed) return `${failed} failed ${hhmm}`;
  return `${last.stopped ? "stopped" : "ok"} ${hhmm}`;
}
