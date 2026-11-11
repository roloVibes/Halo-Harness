// A goal run's one store (the lib/store pattern): the runs of the repo, the run Live draws (the live one, else the
// newest), its event log, the one-file views of its goal files, the focused lane. sync.ts fills it; Live's run block
// (routes/agents/live/runLanes.tsx), the run's inspector (routes/agents/run/) and History's report page read slices with
// useOrch(selector). 3.4.0.0 D "the runs fold": Runs' Start view and its panels' options went with that view.
import { createStore, useStore } from "../../lib/store";
import { settle, type MotionState } from "../../lib/motion";
import type { FileView, RunEvent, RunPayload, RunRow, RunState } from "./types";

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
  /** The runs of the repo have been read once. */
  listed: boolean;
};

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
});

/** A stable empty list for selectors (a new [] per call would re-render forever). */
export const NONE: never[] = [];

export function useOrch<S>(select: (s: OrchState) => S): S {
  return useStore(orch, select);
}

/** The lane the run's inspector is on (its first claimed file becomes the file view's). */
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

/** A run that is still going: running, or waiting on you for its plan. */
export const isLiveRun = (state: RunState | string | undefined): boolean => state === "running" || state === "planned";
