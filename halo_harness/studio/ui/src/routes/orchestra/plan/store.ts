// The plan editor's store (3.0.9.0 R2, the lib/store pattern): the open run's
// jobs as edited, the undo / redo stacks, the problems the last PUT answered,
// the lineup's preflight findings, the claimable units, the selected card and
// whether a request is out. actions.ts changes it; the canvas, the inspector
// and the bar read slices with usePlan(selector).
import { createStore, useStore } from "../../../lib/store";
import type { PlanDecision, PlanFinding, PlanJob, PlanProblem } from "./types";

export type PlanState = {
  runId: string;
  jobs: PlanJob[];
  leadCount: number;
  past: PlanJob[][];
  future: PlanJob[][];
  problems: PlanProblem[];
  preflight: PlanFinding[];
  units: string[];
  sel: string;
  loaded: boolean;
  error: string;
  /** A PUT is out (the problems are about to change). */
  saving: boolean;
  busy: "" | "approve" | "reject";
  /** The Reject card is open (it asks for the reason). */
  rejecting: boolean;
  decision: PlanDecision | null;
};

export const plan = createStore<PlanState>({
  runId: "",
  jobs: [],
  leadCount: 0,
  past: [],
  future: [],
  problems: [],
  preflight: [],
  units: [],
  sel: "",
  loaded: false,
  error: "",
  saving: false,
  busy: "",
  rejecting: false,
  decision: null,
});

export function usePlan<S>(select: (s: PlanState) => S): S {
  return useStore(plan, select);
}

export const NO_JOBS: PlanJob[] = [];

/** Every job a job starts after: its `after` plus each `needs.from`, each once. */
export function upstreams(job: PlanJob): string[] {
  const out = [...(job.after || [])];
  for (const n of job.handoff?.needs || []) if (n.from && !out.includes(n.from)) out.push(n.from);
  return out;
}

/** The problems that name this job. */
export function problemsOf(problems: PlanProblem[], id: string): PlanProblem[] {
  return problems.filter((p) => p.jobs.includes(id));
}

/** What the edge upstream -> job carries (R1's chip): the takes from it, else "after". */
export function edgeLabel(job: PlanJob, upstream: string): string {
  const takes = (job.handoff?.needs || []).filter((n) => n.from === upstream).map((n) => n.take);
  return takes.length ? [...new Set(takes)].join(" + ") : "after";
}

export function selectLane(id: string): void {
  plan.update(() => ({ sel: id }));
}
