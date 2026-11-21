// The Workflows tab's store (3.6.0.0 R2; docs/STUDIO-workflows.md): the list (GET crew/workflows: yours and the
// project's, each with the maps it is on, then the starters), the workflow open in the form and what is saved of it,
// its cost band and what it writes for the form as it stands (POST crew/workflow-cost, a moment after each edit; an
// answer counts only for the form it was asked for -- `costKey` -- so a slow one never shows another form's band), and
// Save / Discard / Copy / Delete through the crew routes (studio/crew_flow_api.py). Nothing is written until Save.
import { api, ApiError } from "../../../lib/api";
import { onFilesChanged, type FilesChange } from "../../../lib/filesLive";
import { createStore, toast, useStore } from "../../../lib/store";
import { TO_A_MAP } from "../map/truthWords";
import type { Cost, FlowRow, Scope, Step, Workflow } from "../types";
import { showFlowTry } from "./flowRun";
import { copyStem, readOnly } from "../scopeTag";

export type FlowState = {
  loaded: boolean;
  error: string;
  flows: FlowRow[];
  starters: FlowRow[];
  open: { name: string; scope: Scope } | null;
  form: Workflow | null;
  saved: Workflow | null;
  maps: string[];
  note: string;
  asking: "" | "delete";
  busy: boolean;
  /** 3.6.0.9 V: the open workflow's file changed on disk while the form held his edits (`gone`: it was removed) */
  stale: boolean;
  gone: boolean;
  /** 3.6.0.9 V: the hash of the file the form was read from or saved to (studio/files_live.py) */
  sig: string;
  cost: Cost | null;
  writes: string[];
  missing: string[];
  problems: string[];
  /** What the band was asked for (keyOf the form then): the band shows only while it is the form's. */
  costKey: string;
  /** "+ Add a step" open: the picker of your agents. */
  adding: boolean;
};

export const flows = createStore<FlowState>({
  loaded: false, error: "", flows: [], starters: [], open: null, form: null, saved: null, maps: [], note: "", asking: "", busy: false,
  stale: false, gone: false, sig: "", cost: null, writes: [], missing: [], problems: [], costKey: "", adding: false,
});
export const useFlows = <T,>(pick: (s: FlowState) => T): T => useStore(flows, pick);

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
export const flowDirty = (s: FlowState) => !!s.form && (!s.saved || !same(s.form, s.saved));
export const blankFlow = (name: string): Workflow => ({ format: "workflow/1", name, for: "", steps: [] });

let watching = false;
let follow: (c: FilesChange) => void = () => undefined;
/** 3.6.0.9 V: the open form follows its file (flowDisk.ts sets it; this store never imports it). */
export const followWith = (fn: (c: FilesChange) => void): void => void (follow = fn);

export async function loadFlows(): Promise<void> {
  if (!watching) {  // 3.6.0.0 R5b: a workflow file written outside Studio shows at once; 3.6.0.9 V: the open one too
    watching = true;
    onFilesChanged(["workflows"], (c) => (void loadFlows(), follow(c)));
    onFilesChanged(["maps"], () => void loadFlows());  // the list's "on the map" tags follow a changed map
  }
  try {
    const r = await api.get<{ workflows: FlowRow[]; starters: FlowRow[] }>("crew/workflows");
    flows.update(() => ({ loaded: true, error: "", flows: r.workflows, starters: r.starters }));
  } catch (e) {
    flows.update(() => ({ loaded: true, error: msg(e) }));
  }
}

function unique(base: string): string {
  const taken = new Set([...flows.get().flows.map((a) => a.name), ...flows.get().starters.map((a) => a.name)]);
  const stem = base.slice(0, 40).replace(/-+$/, "") || "workflow";
  if (!taken.has(stem)) return stem;
  for (let i = 2; ; i++) if (!taken.has(`${stem}-${i}`)) return `${stem}-${i}`;
}

const clean = (w: Workflow): Workflow => ({ format: "workflow/1", name: w.name, for: w.for || "", steps: (w.steps || []).map((s) => ({ ...s })),
  ...(w.own_copy !== undefined ? { own_copy: w.own_copy } : {}), ...(w.max_usd ? { max_usd: w.max_usd } : {}) });

/** What the band depends on: the name, the steps, the cap (equal forms, equal keys, whatever object holds them). */
export const keyOf = (w: Workflow | null): string => (w ? JSON.stringify([w.name, w.steps, w.max_usd ?? null]) : "");
/** The band, what it writes and the missing agents -- of the form as it stands, else nothing (still reading). */
export const costNow = (s: FlowState) => (s.costKey && s.costKey === keyOf(s.form) ? s : null);

let timer = 0;
export function refreshCost(): void {
  window.clearTimeout(timer);
  timer = window.setTimeout(async () => {
    const f = flows.get().form;
    if (!f) return;
    const key = keyOf(f);
    try {
      const r = await api.post<Band>("crew/workflow-cost", { workflow: f });
      if (keyOf(flows.get().form) === key) flows.update(() => bandState(r, key));
    } catch {
      /* the band stays unread; the next edit asks again */
    }
  }, 250);
}

type Band = { cost: Cost; writes: string[]; missing: string[]; problems: string[] };
const bandState = (r: Band, key: string) => ({ cost: r.cost, writes: r.writes, missing: r.missing, problems: r.problems, costKey: key });

/** P batch 2 repair: a saved workflow's band, read before its form is first drawn (the one POST an open makes), so its
 *  lines above Try it and Run it are in the first draw and never push them down after it; null when it cannot be read. */
const bandOf = (w: Workflow): Promise<Band | null> => api.post<Band>("crew/workflow-cost", { workflow: w }).catch(() => null);

/** `band`: read with the open (no second read); undefined: read it now, as an edit does. */
function put(form: Workflow, saved: Workflow | null, open: FlowState["open"], note: string, maps: string[] = [], band?: Band | null, sig = ""): void {
  flows.update(() => ({ form, saved, open, note, maps, asking: "", stale: false, gone: false, sig, adding: false, ...(band ? bandState(band, keyOf(form)) : {}) }));
  if (band === undefined) refreshCost();
}

export async function openFlow(name: string, scope?: Scope): Promise<void> {
  try {
    const r = await api.get<{ workflow: Workflow; scope: Scope; maps: string[]; sig?: string }>(`crew/workflow/${encodeURIComponent(name)}`, scope ? { scope } : undefined);
    const w = clean(r.workflow);
    const band = await bandOf(w);
    put(w, w, { name, scope: r.scope }, "", r.maps, band, r.sig || "");
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export function newFlow(): void {
  put(blankFlow(unique("new-workflow")), null, { name: "", scope: "yours" }, "Not saved yet.");
}

export async function copyFlowFrom(name: string, scope: Scope): Promise<void> {
  try {
    const r = await api.get<{ workflow: Workflow }>(`crew/workflow/${encodeURIComponent(name)}`, { scope });
    const w = clean({ ...r.workflow, name: unique(copyStem(name, scope)) });
    put(w, null, { name: "", scope: "yours" }, `A copy of ${name}, not saved yet: it is yours to change, then Save.`);
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export function setFlow(patch: Partial<Workflow>): void {
  flows.update((s) => (s.form ? { form: { ...s.form, ...patch }, note: "" } : {}));
  refreshCost();
}

const steps = () => [...(flows.get().form?.steps || [])];
export function setStep(i: number, patch: Partial<Step>): void {
  const all = steps();
  const next = { ...all[i], ...patch } as Step & Record<string, unknown>;
  for (const k of Object.keys(patch)) if ((patch as Record<string, unknown>)[k] === undefined) delete next[k];
  all[i] = next;
  setFlow({ steps: all });
}

export function moveStep(i: number, d: number): void {
  const all = steps();
  if (i + d < 0 || i + d >= all.length) return;
  [all[i], all[i + d]] = [all[i + d], all[i]];
  setFlow({ steps: all });
  flows.update(() => ({ note: `Moved "${all[i + d].name}" to step ${i + d + 1}. Not saved yet.` }));
}

export function removeStep(i: number): void {
  const all = steps();
  const [gone] = all.splice(i, 1);
  setFlow({ steps: all });
  flows.update(() => ({ note: `Took out the step "${gone?.name}". Not saved yet.` }));
}

export function addStep(agent: string, does = ""): void {
  const name = (does.split(/[.,:;]/)[0] || agent).trim().slice(0, 60) || agent;
  const all = steps();
  all.push({ name, agents: [agent], gets: all.length ? "what the step before hands on" : "the task", hands: "its result" });
  setFlow({ steps: all });
  flows.update(() => ({ adding: false }));
}

export const setAdding = (on: boolean) => flows.update(() => ({ adding: on }));

export async function saveFlow(): Promise<boolean> {
  const s = flows.get();
  if (!s.form || !s.open || readOnly(s.open.scope)) return false;
  const w = clean(s.form);
  const path = `crew/workflow/${encodeURIComponent(w.name)}`;
  flows.update(() => ({ busy: true }));
  try {
    const r = s.open.name && s.open.name === w.name ? await api.put<{ sig?: string }>(path, { workflow: w })
      : await api.post<{ sig?: string }>(path, { workflow: w });
    let note = `Saved ${w.name}. ${TO_A_MAP} A session's Workflow tool can also run it by its name.`;
    if (s.open.name && s.open.name !== w.name) {
      try {
        await api.del(`crew/workflow/${encodeURIComponent(s.open.name)}`);
        note = `Saved as ${w.name}; ${s.open.name} is gone.`;
      } catch (e) {
        note = `Saved as ${w.name}; ${s.open.name} stays: ${msg(e)}`;
      }
    }
    const now = flows.get().form;
    flows.update(() => ({ open: { name: w.name, scope: s.open!.scope === "project" ? "project" : "yours" }, form: now === s.form ? w : now, saved: w, note, busy: false, stale: false, gone: false, sig: r?.sig || "" }));
    await loadFlows();
    return true;
  } catch (e) {
    flows.update(() => ({ note: msg(e), busy: false }));
    return false;
  }
}

export function discardFlow(): void {
  const s = flows.get();
  if (s.saved) put(s.saved, s.saved, s.open, "Changes discarded.", s.maps);
  else flows.update(() => ({ open: null, form: null, note: "", asking: "" }));
}

export function copyOpenFlow(): void {
  const s = flows.get();
  if (!s.form) return;
  if (s.open?.scope === "pack" && s.open.name) return void copyFlowFrom(s.open.name, "pack"); // 3.6.0.6 P: as a shipped one
  put({ ...s.form, name: unique(`${s.form.name}-copy`) }, null, { name: "", scope: "yours" }, `A copy of ${s.form.name}, not saved yet.`);
}

export const askDeleteFlow = (on: boolean) => flows.update(() => ({ asking: on ? "delete" : "" }));

export async function removeFlow(): Promise<void> {
  const s = flows.get();
  if (!s.open?.name) return discardFlow();
  try {
    await api.del(`crew/workflow/${encodeURIComponent(s.open.name)}`);
    toast(`Deleted ${s.open.name}.`, "done");
    flows.update(() => ({ open: null, form: null, saved: null, note: "", asking: "" }));
    await loadFlows();
  } catch (e) {
    flows.update(() => ({ note: msg(e), asking: "" }));
  }
}

/** An Attention row's open (live/crew_attention.py): the workflow in the form and its run under Try it. */
export async function openFlowTry(name: string, tryId: string): Promise<void> {
  await openFlow(name);
  if (tryId) await showFlowTry(tryId);
}
// The Builder's hooks of this tab (`after`, `onTab`) and what main just built: flowBuilt.ts.
