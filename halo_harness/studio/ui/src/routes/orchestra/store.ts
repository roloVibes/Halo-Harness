// The Orchestra view's one store (the lib/store pattern): the runs of the
// repo, the open run's payload, its event log, the one-file views, the
// focused lane, the view (the Start view or the panels) and the panels' own
// options (remembered in localStorage). sync.ts fills it; the panels read
// slices with useOrch(selector).
import { createStore, useStore, writeLocal } from "../../lib/store";
import { settle, type MotionState } from "../../lib/motion";
import type { FileView, Lane, LaneState, RegionState, RunEvent, RunPayload, RunRow, RunState } from "./types";

export type OrchOptions = {
  elapsed: "relative" | "absolute";
  logLane: number | 0;
  logKinds: string[];
  follow: boolean;
  graphLabels: boolean;
  fileOnlyClaimed: boolean;
};

/** "start": the Start view; "workspace": the panels; "auto": the panels once a run is open. */
export type OrchView = "auto" | "start" | "workspace";

export type OrchState = {
  runs: RunRow[];
  runId: string;
  data: RunPayload | null;
  events: RunEvent[];
  next: number;
  files: Record<string, FileView>;
  file: string;
  focusLane: number | null;
  loading: boolean;
  error: string;
  lastFrame: number;
  doneAt: number;
  started: boolean;
  /** The runs of the repo have been read once (the Start view or the panels can decide). */
  listed: boolean;
  view: OrchView;
  opts: OrchOptions;
};

const OPTS_KEY = "halo.studio.orchestra.opts";
const DEFAULT_OPTS: OrchOptions = {
  elapsed: "relative",
  logLane: 0,
  logKinds: [],
  follow: true,
  graphLabels: true,
  fileOnlyClaimed: false,
};

function readOpts(): OrchOptions {
  try {
    const raw = JSON.parse(localStorage.getItem(OPTS_KEY) || "{}");
    return { ...DEFAULT_OPTS, ...(raw && typeof raw === "object" ? raw : {}) };
  } catch {
    return { ...DEFAULT_OPTS };
  }
}

export const orch = createStore<OrchState>({
  runs: [],
  runId: "",
  data: null,
  events: [],
  next: 0,
  files: {},
  file: "",
  focusLane: null,
  loading: false,
  error: "",
  lastFrame: 0,
  doneAt: 0,
  started: false,
  listed: false,
  view: (/[?&]view=(start|workspace)/.exec(location.search)?.[1] as OrchView) || "auto",
  opts: readOpts(),
});

export function setView(view: OrchView): void {
  orch.update(() => ({ view }));
}

/** Leave the Start view for the panels (the rail or the palette is opening one). */
export function enterWorkspace(): void {
  orch.update((s) => (showsStart(s) ? { view: "workspace" } : {}));
}

/** Whether the Start view shows: asked for, or no run is open once the runs are read. */
export function showsStart(s: OrchState): boolean {
  return s.view === "start" || (s.view === "auto" && s.started && !s.data && !s.loading);
}

/** The runs are being read for the first time (the view waits instead of flashing empty panels). */
export function loadingFirst(s: OrchState): boolean {
  return s.view === "auto" && !s.data && !s.listed;
}

/** A stable empty list for selectors (a new [] per call would re-render forever). */
export const NONE: never[] = [];

export function useOrch<S>(select: (s: OrchState) => S): S {
  return useStore(orch, select);
}

export function setOpt<K extends keyof OrchOptions>(key: K, value: OrchOptions[K]): void {
  const opts = { ...orch.get().opts, [key]: value };
  writeLocal(OPTS_KEY, JSON.stringify(opts));
  orch.update(() => ({ opts }));
}

export function focusLane(n: number | null): void {
  const s = orch.get();
  const lane = s.data?.lanes.find((l) => l.lane === n);
  const file = lane?.claims[0]?.split("#")[0];
  orch.update(() => ({ focusLane: n, ...(file && file !== s.file ? { file } : {}) }));
}

// -- the lane colours: a 10-step ramp built from the tokens (styles/orchestra.css [data-lc]) --
export function laneColor(n: number | null | undefined): string {
  return n ? String((n - 1) % 10) : "";
}

// -- state -> motion (lib/motion's vocabulary) -------------------------------------------
export function runMotion(state: RunState | undefined, doneAt: number): MotionState {
  switch (state) {
    case "running":
      return "working";
    case "finished":
      return settle(doneAt, 1600);
    case "stopped":
      return "error";
    case "interrupted":
    case "planned":
      return "waiting";
    case undefined:
      return "none";
    default:
      return "idle";
  }
}

export function laneMotion(state: LaneState | string): MotionState {
  if (state === "writing" || state === "in_review") return "working";
  if (state === "waiting") return "waiting";
  if (state === "failed") return "error";
  if (state === "merged") return "done";
  return state ? "idle" : "none";
}

export function regionMotion(state: RegionState): MotionState {
  return state === "writing" ? "working" : state === "merged" ? "done" : "idle";
}

export const LANE_LABEL: Record<string, string> = {
  joined: "joined",
  writing: "writing",
  written: "written",
  in_review: "in review",
  waiting: "waiting",
  merged: "merged",
  failed: "failed",
  "": "pending",
};

export type Counters = { joined: number; writing: number; review: number; waiting: number; merged: number; failed: number };

/** The run grid's counters. `joined` counts every lane that has a worktree. */
export function counters(lanes: Lane[]): Counters {
  const c: Counters = { joined: 0, writing: 0, review: 0, waiting: 0, merged: 0, failed: 0 };
  for (const l of lanes) {
    if (l.history.length || l.state) c.joined += 1;
    if (l.state === "writing") c.writing += 1;
    else if (l.state === "in_review" || l.state === "written") c.review += 1;
    else if (l.state === "waiting") c.waiting += 1;
    else if (l.state === "merged") c.merged += 1;
    else if (l.state === "failed") c.failed += 1;
  }
  return c;
}

/** Lane numbers to draw: the lanes that exist, else the workflow's worker steps. */
export function laneSlots(data: RunPayload | null): { n: number; lane: Lane | null; step: string }[] {
  if (!data) return [];
  const steps = (data.workflow?.steps || []).filter((s) => s.kind === "worker" && s.lane);
  const byN = new Map(data.lanes.map((l) => [l.lane, l]));
  const ns = steps.length ? steps.filter((s) => s.state !== "skipped" || byN.has(s.lane!)).map((s) => s.lane!) : [...byN.keys()];
  return ns.map((n) => ({ n, lane: byN.get(n) || null, step: steps.find((s) => s.lane === n)?.state || "pending" }));
}

export function liveNow(data: RunPayload | null): number {
  return data?.live ? Date.now() / 1000 : data?.report?.ts || 0;
}
