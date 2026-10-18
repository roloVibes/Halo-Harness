// The Flow section's one store (the lib/store pattern): the templates and runs,
// the open run's payload and log, the selected step, the gate answers sent
// from here, the org's live positions, and the panels' own options
// (remembered in localStorage). sync.ts fills it; panels read slices with useFlow.
import { createStore, useStore, writeLocal } from "../../lib/store";
import { settle, type MotionState } from "../../lib/motion";
import type { FlowEvent, FlowPayload, FlowRunRow, FlowStatus, LlmRow, StepState, TemplateRow } from "./types";

export type FlowView = "auto" | "start" | "workspace";
export type FlowDefaults = { template: string; platforms: string[]; budget: string; project: string };

export type FlowOptions = {
  elapsed: "relative" | "absolute";
  logStep: string;
  logKinds: string[];
  follow: boolean;
  defaults: FlowDefaults;
};

export type FlowState = {
  templates: TemplateRow[];
  runs: FlowRunRow[];
  runId: string;
  data: FlowPayload | null;
  events: FlowEvent[];
  next: number;
  step: string;
  answered: Record<string, string>;
  positions: Record<string, string>;
  models: LlmRow[];
  loading: boolean;
  error: string;
  lastFrame: number;
  doneAt: number;
  started: boolean;
  /** A template picked in the rail: the intake form switches to it. */
  pick: string;
  /** "start": the Start view; "workspace": the panels; "auto": the panels once a run is open. */
  view: FlowView;
  /** 3.0.9.0 R2: the flow drawn as a graph instead of the section ("Show as graph", ?graph=<name>). */
  graph: string;
  opts: FlowOptions;
};

const OPTS_KEY = "halo.studio.flow.opts";
const DEFAULT_OPTS: FlowOptions = {
  elapsed: "relative",
  logStep: "",
  logKinds: [],
  follow: true,
  defaults: { template: "social-post", platforms: ["x", "instagram"], budget: "", project: "" },
};

function readOpts(): FlowOptions {
  try {
    const raw = JSON.parse(localStorage.getItem(OPTS_KEY) || "{}");
    const o = raw && typeof raw === "object" ? raw : {};
    return { ...DEFAULT_OPTS, ...o, defaults: { ...DEFAULT_OPTS.defaults, ...(o.defaults || {}) } };
  } catch {
    return { ...DEFAULT_OPTS };
  }
}

export const flow = createStore<FlowState>({
  templates: [],
  runs: [],
  runId: "",
  data: null,
  events: [],
  next: 0,
  step: "",
  answered: {},
  positions: {},
  models: [],
  loading: false,
  error: "",
  lastFrame: 0,
  doneAt: 0,
  started: false,
  pick: "",
  view: (/[?&]view=(start|workspace)/.exec(location.search)?.[1] as FlowView) || "auto",
  graph: /[?&]graph=([\w.-]+)/.exec(location.search)?.[1] || "",
  opts: readOpts(),
});

/** Show a saved flow as a graph (FlowGraph.tsx), or "" for the section again. */
export function showGraph(name: string): void {
  flow.update(() => ({ graph: name }));
}

/** A stable empty list for selectors. */
export const NONE: never[] = [];

export function useFlow<S>(select: (s: FlowState) => S): S {
  return useStore(flow, select);
}

export function setOpt<K extends keyof FlowOptions>(key: K, value: FlowOptions[K]): void {
  const opts = { ...flow.get().opts, [key]: value };
  writeLocal(OPTS_KEY, JSON.stringify(opts));
  flow.update(() => ({ opts }));
}

export function selectStep(id: string): void {
  flow.update(() => ({ step: id }));
}

export function pickTemplate(name: string): void {
  flow.update(() => ({ pick: name }));
}

export function setView(view: FlowView): void {
  flow.update(() => ({ view }));
}

/** Leave the Start view for the panels (the rail or the palette is opening one). */
export function enterWorkspace(): void {
  flow.update((s) => (showsStart(s) ? { view: "workspace" } : {}));
}

/** Whether the Start view shows: asked for, or no run is open (and none is loading). */
export function showsStart(s: FlowState): boolean {
  return s.view === "start" || (s.view === "auto" && !s.data && !s.loading);
}

/** The step the Step panel shows: the one picked, else the waiting one, the running one, the last done. */
export function currentStep(s: FlowState): string {
  const steps = s.data?.flow.steps || [];
  if (s.step && steps.some((x) => x.id === s.step)) return s.step;
  const pick = steps.find((x) => x.state === "waiting") || steps.find((x) => x.state === "running") || steps.find((x) => x.state === "failed");
  if (pick) return pick.id;
  const done = steps.filter((x) => x.state === "done" && x.kind !== "done");
  return (done[done.length - 1] || steps[0])?.id || "";
}

// -- state -> motion (lib/motion's vocabulary) ---------------------------------------
export function stepMotion(state: StepState | undefined): MotionState {
  if (state === "running") return "working";
  if (state === "waiting") return "waiting";
  if (state === "failed") return "error";
  if (state === "done") return "done";
  return "none";
}

export function runMotion(status: FlowStatus | undefined, waiting: boolean, doneAt: number): MotionState {
  if (waiting) return "waiting";
  if (status === "running") return "working";
  if (status === "finished") return settle(doneAt, 1600);
  if (status === "failed" || status === "stopped") return "error";
  return status ? "idle" : "none";
}

/** The run's state word: "waiting" while a gate is open, else flow.json's status. */
export function runState(s: FlowState): FlowStatus | undefined {
  if (!s.data) return undefined;
  return s.data.gate ? "waiting" : s.data.report?.status || s.data.flow.status;
}

/** `"n/m"`: steps finished of the run's steps (a string, so a selector's answer stays stable). */
export function stepCount(s: FlowState): string {
  const steps = s.data?.flow.steps || [];
  return `${steps.filter((x) => x.state === "done" || x.state === "skipped").length}/${steps.length}`;
}

export function platformsOf(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(String).filter(Boolean);
  return String(v || "")
    .split(/[,\s]+/)
    .map((x) => x.trim())
    .filter(Boolean);
}

/** The template's platform choices (its intake form's `platforms` list). */
export function platformChoices(t: TemplateRow | undefined): string[] {
  const p = t?.form?.platforms;
  return Array.isArray(p) && p.length ? p.map(String) : ["x", "instagram", "youtube", "tiktok", "linkedin"];
}
