// The Media panels' store (ComfyUI through studio/media_api.py): the server
// status (refreshed every 15 s while a Media panel is on screen), the cached
// model inventory, the workflows and one workflow's inputs (3.3.13.0 R2: the renders into a design project went
// with Design to its pack).
import { api, ApiError } from "../../lib/api";
import { createStore, toast, useStore, writeLocal } from "../../lib/store";

export type Gpu = { name: string; type?: string; vram_total?: number | null; vram_free?: number | null };
export type MediaStatus = {
  url: string;
  reachable: boolean | null;
  version?: string | null;
  gpus?: Gpu[];
  registered?: { command?: string; args?: string[]; url?: string | null } | null;
  error?: string | null;
  age_s?: number | null;
  checking?: boolean;
  cache?: { scanned: number | null; age_s: number | null; rows: number; workflows: number };
};
export type MediaModel = {
  ref: string;
  kind: string;
  file: string;
  folder?: string;
  family?: string;
  quant?: string;
  size_bytes?: number | null;
  modalities_in?: string[];
  modalities_out?: string[];
  notes?: string;
};
export type Workflow = { name: string; source: "starter" | "saved" | string };
export type InputNode = { node: string; class_type: string; title?: string; inputs: Record<string, unknown>; keys?: Record<string, string> };

export type MediaState = {
  status: MediaStatus | null;
  statusAt: number;
  models: MediaModel[];
  tab: string;
  workflows: Workflow[];
  wfReachable: boolean | null;
  inputsOf: Workflow | null;
  inputs: InputNode[];
  inputsError: string;
  scanning: boolean;
  started: boolean;
};

const TAB_KEY = "halo.studio.media.tab";
export const TABS: { id: string; label: string; kinds: string[] }[] = [
  { id: "image", label: "image", kinds: ["image-gen"] },
  { id: "video", label: "video", kinds: ["video-gen"] },
  { id: "audio", label: "audio", kinds: ["tts", "audio-gen"] },
  { id: "upscale", label: "upscale", kinds: ["upscale"] },
];
export const SUPPORTING = ["encoder", "lora", "vae", "other"];

function savedTab(): string {
  try {
    const t = localStorage.getItem(TAB_KEY) || "";
    return TABS.some((x) => x.id === t) ? t : "image";
  } catch {
    return "image";
  }
}

export const media = createStore<MediaState>({
  status: null,
  statusAt: 0,
  models: [],
  tab: savedTab(),
  workflows: [],
  wfReachable: null,
  inputsOf: null,
  inputs: [],
  inputsError: "",
  scanning: false,
  started: false,
});

export function useMedia<S>(select: (s: MediaState) => S): S {
  return useStore(media, select);
}

export function setTab(tab: string): void {
  writeLocal(TAB_KEY, tab);
  media.update(() => ({ tab }));
}

const text = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

export async function loadStatus(): Promise<void> {
  try {
    const status = await api.get<MediaStatus>("media/status");
    media.update(() => ({ status, statusAt: Date.now() }));
  } catch (e) {
    media.update((s) => ({ status: { url: s.status?.url || "", reachable: false, error: text(e) }, statusAt: Date.now() }));
  }
}

export async function loadModels(): Promise<void> {
  try {
    const r = await api.get<{ rows: MediaModel[] }>("media/models", { kind: "all" });
    media.update(() => ({ models: Array.isArray(r.rows) ? r.rows : [] }));
  } catch {
    /* the status panel says why */
  }
}

export async function loadWorkflows(): Promise<void> {
  try {
    const r = await api.get<{ workflows: Workflow[]; reachable: boolean }>("media/workflows");
    media.update(() => ({ workflows: r.workflows || [], wfReachable: !!r.reachable }));
  } catch {
    media.update(() => ({ wfReachable: false }));
  }
}

/** Read the server's model folders and saved workflows into the cache (POST media/scan). */
export async function scan(): Promise<void> {
  media.update(() => ({ scanning: true }));
  try {
    const r = await api.post<{ rows: number; workflows: string[] }>("media/scan");
    toast(`Scanned ComfyUI: ${r.rows} model file(s), ${(r.workflows || []).length} saved workflow(s)`, "done");
  } catch (e) {
    toast(`Scan: ${text(e)}`, "error", 5000);
  }
  media.update(() => ({ scanning: false }));
  await Promise.all([loadStatus(), loadModels(), loadWorkflows()]);
}

export async function openInputs(w: Workflow): Promise<void> {
  media.update(() => ({ inputsOf: w, inputs: [], inputsError: "" }));
  try {
    const r = await api.get<{ nodes: InputNode[] }>(`media/workflows/${encodeURIComponent(w.name)}/inputs`, { source: w.source });
    if (media.get().inputsOf === w) media.update(() => ({ inputs: r.nodes || [] }));
  } catch (e) {
    if (media.get().inputsOf === w) media.update(() => ({ inputsError: text(e) }));
  }
}

let timer = 0;
let mounted = 0;
/** Start once; while any Media panel is mounted the status refreshes every 15 s. Returns the unmount. */
export function attachMedia(): () => void {
  mounted += 1;
  if (!media.get().started) {
    media.update(() => ({ started: true }));
    void Promise.all([loadStatus(), loadModels(), loadWorkflows()]);
  }
  if (!timer) timer = window.setInterval(() => void loadStatus(), 15000);
  return () => {
    mounted -= 1;
    if (mounted <= 0 && timer) {
      window.clearInterval(timer);
      timer = 0;
    }
  };
}

export function gib(bytes: number | null | undefined): string {
  const v = Number(bytes) || 0;
  if (v >= 1024 ** 3) return `${(v / 1024 ** 3).toFixed(1)} GB`;
  if (v >= 1024 ** 2) return `${(v / 1024 ** 2).toFixed(0)} MB`;
  return v ? `${(v / 1024).toFixed(0)} KB` : "-";
}

export function ago(s: number | null | undefined): string {
  if (s === null || s === undefined) return "never";
  if (s < 90) return `${Math.round(s)}s ago`;
  if (s < 5400) return `${Math.round(s / 60)}m ago`;
  if (s < 172800) return `${Math.round(s / 3600)}h ago`;
  return `${Math.round(s / 86400)}d ago`;
}
