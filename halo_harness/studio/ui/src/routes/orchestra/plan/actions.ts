// The plan editor's actions (3.0.9.0 R2): load the plan (GET orchestra/<run>/
// plan), every edit through `edit()` (one undo step, then a PUT of the draft
// 250 ms after the last one, whose answer is the problems), undo / redo, add
// and drop a lane, move a lane into another layer box (its `after` is
// rewritten), approve (POST approve; the console returns once the run moves
// on; a forecast over the budget comes back as a warning) and reject with a reason.
import { api, ApiError } from "../../../lib/api";
import { toast } from "../../../lib/store";
import { orch } from "../store";
import { refresh } from "../sync";
import { layersOf } from "./layout";
import { plan, upstreams } from "./store";
import type { Forecast, PlanJob, PlanPayload, PlanProblem } from "./types";

const UNDO_MAX = 100;
let timer = 0;

const clone = (jobs: PlanJob[]): PlanJob[] => JSON.parse(JSON.stringify(jobs));
const path = (what = "plan") => `orchestra/${encodeURIComponent(plan.get().runId)}/${what}`;

export async function loadPlan(runId: string): Promise<void> {
  plan.update((s) => ({ runId, loaded: false, error: "", past: [], future: [], rejecting: false, staged: s.runId === runId ? s.staged : "" }));
  try {
    const p = await api.get<PlanPayload>(`orchestra/${encodeURIComponent(runId)}/plan`);
    if (plan.get().runId !== runId) return;
    plan.update((s) => ({
      jobs: p.jobs,
      leadCount: p.lead_jobs.length,
      problems: p.problems,
      preflight: p.preflight,
      units: p.units,
      decision: p.decision,
      forecast: p.forecast || null,
      loaded: true,
      sel: p.jobs.some((j) => j.id === s.sel) ? s.sel : p.jobs[0]?.id || "",
    }));
  } catch (e) {
    plan.update(() => ({ loaded: true, error: e instanceof ApiError ? e.message : String(e) }));
  }
}

export async function savePlan(): Promise<void> {
  const { runId, jobs } = plan.get();
  if (!runId) return;
  try {
    const r = await api.put<{ ok: boolean; problems: PlanProblem[]; forecast?: Forecast }>(path(), { jobs });
    if (plan.get().runId === runId && plan.get().jobs === jobs)
      plan.update((s) => ({ problems: r.problems, saving: false, forecast: r.forecast || s.forecast }));
  } catch (e) {
    plan.update(() => ({ saving: false, error: e instanceof ApiError ? e.message : String(e) }));
  }
}

function saveSoon(): void {
  if (plan.get().staged) return; // 3.0.9.0 R3: a staged coach edit is shown, never sent
  plan.update(() => ({ saving: true }));
  window.clearTimeout(timer);
  timer = window.setTimeout(() => void savePlan(), 250);
}

/** One edit: `fn` gets a copy of the jobs and returns the new list. */
export function edit(fn: (jobs: PlanJob[]) => PlanJob[]): void {
  const s = plan.get();
  const next = fn(clone(s.jobs));
  plan.update(() => ({ jobs: next, past: [...s.past, s.jobs].slice(-UNDO_MAX), future: [] }));
  saveSoon();
}

export function patchJob(id: string, patch: Partial<PlanJob>): void {
  edit((jobs) => jobs.map((j) => (j.id === id ? { ...j, ...patch } : j)));
}

export function undo(): void {
  const s = plan.get();
  if (!s.past.length) return;
  plan.update(() => ({ jobs: s.past[s.past.length - 1], past: s.past.slice(0, -1), future: [s.jobs, ...s.future] }));
  saveSoon();
}

export function redo(): void {
  const s = plan.get();
  if (!s.future.length) return;
  plan.update(() => ({ jobs: s.future[0], future: s.future.slice(1), past: [...s.past, s.jobs] }));
  saveSoon();
}

export function addLane(): void {
  const n = Math.max(0, ...plan.get().jobs.map((j) => Number(/(\d+)$/.exec(j.id)?.[1] || 0))) + 1;
  const id = `job-${n}`;
  edit((jobs) => [...jobs, { id, title: "", claims: [] }]);
  plan.update(() => ({ sel: id }));
}

/** Drop a lane; every reference to it goes too. */
export function dropLane(id: string): void {
  edit((jobs) =>
    jobs
      .filter((j) => j.id !== id)
      .map((j) => {
        const needs = (j.handoff?.needs || []).filter((n) => n.from !== id);
        return { ...j, after: (j.after || []).filter((a) => a !== id), handoff: { ...(j.handoff || {}), needs } };
      }),
  );
  const left = plan.get().jobs;
  plan.update((s) => ({ sel: s.sel === id ? left[0]?.id || "" : s.sel }));
}

export function layerMap(jobs: PlanJob[]): Record<string, number> {
  return layersOf(jobs.map((j) => j.id), Object.fromEntries(jobs.map((j) => [j.id, upstreams(j)])));
}

/** Drag into box `k`: box 0 clears its after (and its needs); box k runs after every lane of box k-1. */
export function moveToLayer(id: string, k: number): void {
  const jobs = plan.get().jobs;
  const others = jobs.filter((j) => j.id !== id);
  const layer = layerMap(others);
  const before = new Set(others.filter((j) => (layer[j.id] || 0) < k).map((j) => j.id));
  const prev = others.filter((j) => (layer[j.id] || 0) === k - 1).map((j) => j.id);
  edit((list) =>
    list.map((j) => {
      if (j.id !== id) return j;
      const needs = k === 0 ? [] : (j.handoff?.needs || []).filter((n) => before.has(n.from));
      return { ...j, after: k === 0 ? [] : prev, handoff: { ...(j.handoff || {}), needs } };
    }),
  );
}

async function decided(): Promise<void> {
  await refresh();
  for (let i = 0; i < 20 && orch.get().data?.run.state === "planned"; i++) {
    await new Promise((r) => window.setTimeout(r, 250));
    await refresh();
  }
}

export async function approve(): Promise<void> {
  window.clearTimeout(timer);
  plan.update(() => ({ busy: "approve" }));
  try {
    const r = await api.post<{ warning?: string }>(path("approve"), { jobs: plan.get().jobs });
    toast(`Plan approved: run ${plan.get().runId} goes on`, "done");
    if (r?.warning) toast(`Over budget: ${r.warning}`, "info", 6000); // 3.1.2.0 R2: Approve warns, it does not refuse
    await decided();
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) {
      const rows = e.data.problems;
      if (Array.isArray(rows)) plan.update(() => ({ problems: rows as PlanProblem[] }));
    }
    toast(e instanceof ApiError ? e.message : String(e), "error", 5000);
  }
  plan.update(() => ({ busy: "" }));
}

export async function reject(reason: string): Promise<void> {
  plan.update(() => ({ busy: "reject" }));
  try {
    await api.post(path("reject"), { reason });
    toast(`Plan rejected: run ${plan.get().runId} stops`, "info");
    plan.update(() => ({ rejecting: false }));
    await decided();
  } catch (e) {
    toast(e instanceof ApiError ? e.message : String(e), "error", 5000);
  }
  plan.update(() => ({ busy: "" }));
}
