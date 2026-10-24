// A pack's workflow on Orchestra's new-run form (3.2.0.0 R6): the Pack
// Manager's "Run <workflow>" opens the Orchestra Start view with the form
// filled in -- the workflow (`<pack>/<name>`), its inputs with their types,
// defaults and help -- and Run posts `orchestra/run {workflow, inputs, model}`,
// which compiles it exactly as `halo workflow run` does (a 422 lists the
// compile's lines under the form). "A blank goal instead" clears it.
import { api, ApiError } from "../../lib/api";
import { createStore, goSection, toast, useStore } from "../../lib/store";
import type { PackWorkflow } from "../packs/manager/types";
import { setView } from "./store";
import { loadRuns, openRun } from "./sync";

export type WfRun = { wf: PackWorkflow | null; values: Record<string, string> };

export const wfRun = createStore<WfRun>({ wf: null, values: {} });

export function useWfRun<S>(select: (s: WfRun) => S): S {
  return useStore(wfRun, select);
}

const text = (v: unknown) => (v === null || v === undefined ? "" : String(v));

/** Open Orchestra's Start view with `wf` filled in (each input at its default). */
export function runWorkflow(wf: PackWorkflow): void {
  wfRun.update(() => ({ wf, values: Object.fromEntries(wf.inputs.map((i) => [i.name, text(i.default)])) }));
  goSection("orchestra");
  setView("start");
}

export function clearWorkflow(): void {
  wfRun.update(() => ({ wf: null, values: {} }));
}

export function setInput(name: string, value: string): void {
  wfRun.update((s) => ({ values: { ...s.values, [name]: value } }));
}

/** Compile and run it; `[]` when it started (the run opens), else the lines to show. */
export async function startWorkflow(model: string): Promise<string[]> {
  const { wf, values } = wfRun.get();
  if (!wf) return ["no workflow is filled in"];
  try {
    const inputs = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim() !== ""));
    const r = await api.post<{ run_id: string }>("orchestra/run", { workflow: wf.ref, inputs, ...(model ? { model } : {}) });
    toast(`Workflow ${wf.ref}: run ${r.run_id} started`, "info");
    clearWorkflow();
    await loadRuns();
    await openRun(r.run_id);
    return [];
  } catch (e) {
    if (e instanceof ApiError) return e.problems.length ? e.problems : [e.message];
    return [String(e)];
  }
}
