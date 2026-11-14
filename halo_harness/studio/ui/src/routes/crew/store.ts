// The Agents tab's store (3.6.0.0 R1): the list (GET crew/agents: yours and the project's, then the starters), the
// agent open in the form and what is saved of it, Save / Discard / Copy / Delete through the crew routes
// (studio/crew_api.py). Nothing is written until Save; Delete asks on the page first. Try it lives in tryStore.ts.
import { api, ApiError } from "../../lib/api";
import { createStore, toast, useStore } from "../../lib/store";
import { blank, type Agent, type Row, type Scope } from "./types";

export type CrewState = {
  loaded: boolean;
  error: string;
  agents: Row[];
  starters: Row[];
  /** The agent in the form: its name on disk ("" for one not saved yet) and its scope. */
  open: { name: string; scope: Scope } | null;
  form: Agent | null;
  saved: Agent | null;
  used: string[];
  note: string;
  asking: "" | "delete";
  busy: boolean;
  /** The builder changed the open agent while the form had edits: Reload offers what is on disk. */
  stale: boolean;
  /** 3.6.0.0 R2: the workflow this agent was made for ("make it" / "+ Add a step" -> a new agent): Save goes back there. */
  returnTo: string;
};

export const crew = createStore<CrewState>({
  loaded: false, error: "", agents: [], starters: [], open: null, form: null, saved: null, used: [], note: "", asking: "", busy: false, stale: false,
  returnTo: "",
});
export const useCrew = <T,>(pick: (s: CrewState) => T): T => useStore(crew, pick);

const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

export function dirty(s: CrewState): boolean {
  return !!s.form && (!s.saved || !same(s.form, s.saved));
}

export async function loadCrew(): Promise<void> {
  try {
    const r = await api.get<{ agents: Row[]; starters: Row[] }>("crew/agents");
    crew.update(() => ({ loaded: true, error: "", agents: r.agents, starters: r.starters }));
  } catch (e) {
    crew.update(() => ({ loaded: true, error: msg(e) }));
  }
}

function unique(base: string): string {
  const taken = new Set([...crew.get().agents.map((a) => a.name), ...crew.get().starters.map((a) => a.name)]);
  const stem = base.slice(0, 40).replace(/-+$/, "") || "agent";
  if (!taken.has(stem)) return stem;
  for (let i = 2; ; i++) if (!taken.has(`${stem}-${i}`)) return `${stem}-${i}`;
}

function clean(a: Agent): Agent {
  const more = Object.fromEntries(Object.entries(a.more || {}).filter(([, v]) => v !== undefined && v !== "" && !(Array.isArray(v) && !v.length)));
  return { ...a, format: "agent/1", more };
}

export async function openAgent(name: string, scope?: Scope): Promise<void> {
  try {
    const r = await api.get<{ agent: Agent; scope: Scope; used: string[] }>(`crew/agent/${encodeURIComponent(name)}`, scope ? { scope } : undefined);
    const a = clean(r.agent);
    crew.update(() => ({ open: { name, scope: r.scope }, form: a, saved: a, used: r.used, note: "", asking: "", stale: false, returnTo: "" }));
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export function newAgent(): void {
  const a = blank(unique("new-agent"));
  crew.update(() => ({ open: { name: "", scope: "yours" }, form: a, saved: null, used: [], note: "Not saved yet.", asking: "", stale: false, returnTo: "" }));
}

let back: ((agent: string, workflow: string) => void) | null = null;
/** 3.6.0.0 R2: what Save does for an agent made for a workflow (routes/crew/flows/makeIt.ts: back to the Workflows tab). */
export function onSavedFor(fn: (agent: string, workflow: string) => void): void {
  back = fn;
}

/** 3.6.0.0 R2: the agent form filled in for a workflow (a proposal's "make it", or "+ Add a step" -> a new agent). */
export function fillAgent(a: Agent, workflow: string): void {
  const form = clean({ ...blank(a.name), ...a });
  crew.update(() => ({ open: { name: "", scope: "yours" }, form, saved: null, used: [], asking: "", stale: false, returnTo: workflow,
    note: `Made for the workflow ${workflow}, not saved yet: read it, change what you like, Save -- you go back to the workflow.` }));
}

export async function copyFrom(name: string, scope: Scope): Promise<void> {
  try {
    const r = await api.get<{ agent: Agent }>(`crew/agent/${encodeURIComponent(name)}`, { scope });
    const a = clean({ ...r.agent, name: unique(scope === "starter" ? `my-${name}` : `${name}-copy`) });
    crew.update(() => ({ open: { name: "", scope: "yours" }, form: a, saved: null, used: [], asking: "", stale: false,
      note: `A copy of ${name}, not saved yet: it is yours to change, then Save.` }));
  } catch (e) {
    toast(msg(e), "error", 5000);
  }
}

export function setForm(patch: Partial<Agent>): void {
  crew.update((s) => (s.form ? { form: { ...s.form, ...patch }, note: "" } : {}));
}

export function setMore(patch: Partial<NonNullable<Agent["more"]>>): void {
  crew.update((s) => (s.form ? { form: { ...s.form, more: { ...(s.form.more || {}), ...patch } }, note: "" } : {}));
}

export async function save(): Promise<boolean> {
  const s = crew.get();
  if (!s.form || !s.open || s.open.scope === "starter") return false;
  const a = clean(s.form);
  const path = `crew/agent/${encodeURIComponent(a.name)}`;
  crew.update(() => ({ busy: true }));
  try {
    if (s.open.name && s.open.name === a.name) await api.put(path, { agent: a });
    else await api.post(path, { agent: a });
    let note = `Saved ${a.name}.`;
    if (s.open.name && s.open.name !== a.name) {
      try {
        await api.del(`crew/agent/${encodeURIComponent(s.open.name)}`);
        note = `Saved as ${a.name}; ${s.open.name} is gone.`;
      } catch (e) {
        note = `Saved as ${a.name}; ${s.open.name} stays: ${msg(e)}`;
      }
    }
    const now = crew.get().form; // an edit made while the save was on its way stays (and the form reads dirty again)
    crew.update(() => ({ open: { name: a.name, scope: s.open!.scope === "project" ? "project" : "yours" }, form: now === s.form ? a : now, saved: a, note, busy: false, stale: false }));
    await loadCrew();
    if (s.returnTo && back) {
      crew.update(() => ({ returnTo: "" }));
      back(a.name, s.returnTo);
    }
    return true;
  } catch (e) {
    crew.update(() => ({ note: msg(e), busy: false }));
    return false;
  }
}

export function discard(): void {
  const s = crew.get();
  if (s.saved) crew.update(() => ({ form: s.saved, note: "Changes discarded.", asking: "", stale: false }));
  else crew.update(() => ({ open: null, form: null, note: "", asking: "" }));
}

export function copyOpen(): void {
  const s = crew.get();
  if (!s.form) return;
  const a = { ...s.form, name: unique(`${s.form.name}-copy`) };
  crew.update(() => ({ open: { name: "", scope: "yours" }, form: a, saved: null, used: [], note: `A copy of ${s.form!.name}, not saved yet.`, asking: "" }));
}

export const askDelete = (on: boolean) => crew.update(() => ({ asking: on ? "delete" : "" }));

export async function remove(): Promise<void> {
  const s = crew.get();
  if (!s.open?.name) return discard();
  try {
    await api.del(`crew/agent/${encodeURIComponent(s.open.name)}`);
    toast(`Deleted ${s.open.name}.`, "done");
    crew.update(() => ({ open: null, form: null, saved: null, note: "", asking: "" }));
    await loadCrew();
  } catch (e) {
    crew.update(() => ({ note: msg(e), asking: "" }));
  }
}

/** After the builder applied: the list again, and the open agent from disk unless the form holds edits. */
export async function afterApply(touched: string[]): Promise<void> {
  await loadCrew();
  const s = crew.get();
  if (!s.open?.name || !touched.includes(s.open.name)) return;
  if (dirty(s)) crew.update(() => ({ stale: true }));
  else if (crew.get().agents.some((a) => a.name === s.open!.name)) await openAgent(s.open.name, s.open.scope);
  else crew.update(() => ({ open: null, form: null, saved: null }));
}

export function selectionName(): string {
  return crew.get().form?.name || "";
}
