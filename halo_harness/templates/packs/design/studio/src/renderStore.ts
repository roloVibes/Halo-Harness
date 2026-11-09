// The Render panel's store (3.0.4.0 R5's Media render, the design pack's since 3.3.13.0 R2): the workflows the core's
// media routes list (`media/workflows`, a starter or one saved on ComfyUI) and one's inputs, the renders started here
// and their state. A render is the pack's `POST render`; its steps are the pack's live frames of kind `render`; each
// output lands as an artboard of the project (Artboards reloads when one is done).
import { api, ApiError } from "@halo/api";
import { onEvent, type FeedFrame } from "@halo/events";
import { createStore, toast, useStore } from "@halo/store";
import { BASE, PACK, rawUrl } from "./base";
import { reload } from "./sync";

export type Workflow = { name: string; source: "starter" | "saved" | string };
export type InputNode = { node: string; class_type: string; title?: string; inputs: Record<string, unknown>; keys?: Record<string, string> };
export type RenderArt = { id: string; kind?: string; url?: string; version?: number; bytes?: number };
export type RenderState = { prompt_id: string; state: string; text?: string; project?: string; artboard?: string; workflow?: string;
  artboards?: RenderArt[]; error?: string; at?: number };
type State = { started: boolean; workflows: Workflow[]; inputsOf: Workflow | null; inputs: InputNode[]; inputsError: string;
  renders: Record<string, RenderState>; current: string };

export const renders = createStore<State>({ started: false, workflows: [], inputsOf: null, inputs: [], inputsError: "", renders: {}, current: "" });

export function useRenders<S>(select: (s: State) => S): S {
  return useStore(renders, select);
}

const text = (e: unknown) => (e instanceof ApiError ? e.problems[0] || e.message : String(e));

/** An output's address: the server says `_files/<slug>/<aid>/<file>`, under the pack's routes, its key in ?k=. */
export const artUrl = (a: RenderArt) => (a.url ? rawUrl(a.url.replace(/^_files\//, "")) : "");

function onFrame(f: FeedFrame): void {
  const live = (f.data || {}) as { pack?: string; kind?: string; data?: RenderState };
  if (live.pack !== PACK || live.kind !== "render" || !live.data?.prompt_id) return;
  const d = live.data;
  renders.update((s) => ({ renders: { ...s.renders, [d.prompt_id]: { ...s.renders[d.prompt_id], ...d, at: Date.now() } } }));
  if (d.state === "done") (toast(`Render ${d.prompt_id} done: ${d.text || ""}`, "done"), void reload());
  if (d.state === "error") toast(`Render ${d.prompt_id}: ${d.error || d.text}`, "error", 5000);
}

export async function openInputs(w: Workflow): Promise<void> {
  renders.update(() => ({ inputsOf: w, inputs: [], inputsError: "" }));
  try {
    const r = await api.get<{ nodes: InputNode[] }>(`media/workflows/${encodeURIComponent(w.name)}/inputs`, { source: w.source });
    if (renders.get().inputsOf === w) renders.update(() => ({ inputs: r.nodes || [] }));
  } catch (e) {
    if (renders.get().inputsOf === w) renders.update(() => ({ inputsError: text(e) }));
  }
}

/** Start once: the frames and the workflows. */
export function startRenders(): void {
  if (renders.get().started) return;
  renders.update(() => ({ started: true }));
  onEvent("pack_live", onFrame);
  void api.get<{ workflows: Workflow[] }>("media/workflows").then(
    (r) => renders.update(() => ({ workflows: r.workflows || [] })),
    () => renders.update(() => ({ workflows: [] })),
  );
}

/** The pack's POST render -> 202 {prompt_id}; the frames fill in the rest. Returns the problems, if any. */
export async function render(w: Workflow, set: Record<string, unknown>, project: string, artboard: string): Promise<string[]> {
  try {
    const r = await api.post<{ prompt_id: string }>(`${BASE}/render`, { workflow: w.name, source: w.source, set, project, artboard });
    const row: RenderState = { prompt_id: r.prompt_id, state: "queued", text: `queued ${w.name}`, project, artboard, workflow: w.name, at: Date.now() };
    renders.update((s) => ({ renders: { ...s.renders, [r.prompt_id]: { ...row, ...s.renders[r.prompt_id] } }, current: r.prompt_id }));
    toast(`Render ${r.prompt_id} queued`, "info");
    return [];
  } catch (e) {
    return e instanceof ApiError && e.problems.length ? e.problems : [text(e)];
  }
}
