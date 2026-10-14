// The Flow section's actions: start a run (with assets: make it without
// starting, upload each file, then resume it), answer the open gate, stop and
// resume a run, and the LLM rows for the model select. Each posts to the
// flow routes (studio/flow_api.py) and refreshes the store.
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { flow } from "./store";
import { errorText, loadEvents, loadRuns, openRun, refresh, runPath } from "./sync";
import type { LlmRow } from "./types";

export type RunMode = "run" | "yes" | "dry";

export type IntakeForm = {
  template: string;
  brief: string;
  platforms: string[];
  budget: string;
  project: string;
  model: string;
  /** `[key, value]` rows: `render.width` = `64`. */
  set: [string, string][];
  files: File[];
};

function base64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).replace(/^data:[^,]*,/, ""));
    r.onerror = () => reject(r.error || new Error("could not read " + file.name));
    r.readAsDataURL(file);
  });
}

function overrides(form: IntakeForm, mode: RunMode): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of form.set) {
    if (!k.trim() || v === "") continue;
    out[k.trim()] = /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : v === "true" ? true : v === "false" ? false : v;
  }
  if (mode === "dry") {
    const t = flow.get().templates.find((x) => x.name === form.template);
    for (const s of t?.steps || []) if (s.kind === "post") out[`${s.id}.live`] = false;
  }
  return out;
}

/** Start a run; returns the problems to show under the form (empty when it started). */
export async function startRun(form: IntakeForm, mode: RunMode): Promise<string[]> {
  const intake: Record<string, unknown> = { brief: form.brief, platforms: form.platforms };
  if (form.budget.trim()) intake.budget_usd = form.budget.trim();
  if (form.project.trim()) intake.project = form.project.trim();
  const body = {
    template: form.template,
    intake,
    ...(form.model ? { model: form.model } : {}),
    set: overrides(form, mode),
    yes: mode === "yes",
    start: !form.files.length,
  };
  try {
    const r = await api.post<{ run: string; started: boolean; warnings: string[] }>("flow/runs", body);
    for (const f of form.files) {
      await api.post(runPath(r.run, "/assets"), { name: f.name, data_base64: await base64(f) });
    }
    if (form.files.length) await api.post(runPath(r.run, "/resume"), { ...(form.model ? { model: form.model } : {}), yes: mode === "yes" });
    toast(`${mode === "dry" ? "Dry run" : "Run"} ${r.run} started${form.files.length ? ` with ${form.files.length} asset(s)` : ""}`, "info");
    for (const w of r.warnings || []) toast(w, "info", 5000);
    await loadRuns();
    await openRun(r.run);
    return [];
  } catch (e) {
    if (e instanceof ApiError) return e.problems.length ? e.problems : [e.message];
    return [String(e)];
  }
}

/** Answer the open gate: accept, redo (with the instruction) or stop. */
export async function answerGate(action: "accept" | "redo" | "stop", instruction = ""): Promise<boolean> {
  const { runId, data } = flow.get();
  const gate = data?.gate;
  if (!runId || !gate) return false;
  try {
    const r = await api.post<{ message: string }>(runPath(runId, "/answer"), { step: gate.step, action, instruction, round: gate.round });
    flow.update((s) => ({ answered: { ...s.answered, [`${runId}:${gate.step}:${gate.round}`]: action } }));
    toast(r.message || `${gate.step}: ${action}`, action === "stop" ? "error" : "done");
  } catch (e) {
    toast(errorText(e), "error", 5000);
    return false;
  }
  await refresh();
  await loadEvents();
  return true;
}

async function act(path: string, body: Record<string, unknown>, done: string): Promise<void> {
  const id = flow.get().runId;
  if (!id) return;
  try {
    await api.post(runPath(id, path), body);
    toast(done, "done");
  } catch (e) {
    toast(errorText(e), "error", 5000);
  }
  await refresh();
  await loadEvents();
  await loadRuns();
}

export const stopRun = () => act("/stop", { reason: "stopped from Studio" }, "Stop requested: the run stops at its next step");
export const resumeRun = (yes = false) => act("/resume", { yes }, "Resumed");

let modelsAsked = false;
/** The LLM rows (GET models), once, for the intake's model select. */
export function loadModels(): void {
  if (modelsAsked) return;
  modelsAsked = true;
  api
    .get<LlmRow[]>("models")
    .then((rows) => flow.update(() => ({ models: Array.isArray(rows) ? rows : [] })))
    .catch(() => {
      modelsAsked = false;
    });
}
