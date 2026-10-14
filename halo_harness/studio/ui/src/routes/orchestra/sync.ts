// Feeds the Orchestra store: `GET orchestra/runs` and `GET orchestra/<run>`
// on load, then the live feed's `orchestra_*` frames (lib/events onEvent):
// a frame of the open run refreshes the payload and the log (debounced), a
// claim or merge frame refetches the open file view, a frame of another run
// refreshes the run list. Polling (5 s) only while the feed is not open and
// the run is live. The actions post to the routes and refresh.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { studio, toast } from "../../lib/store";
import { orch } from "./store";
import type { FileView, RunEvent, RunPayload, RunRow } from "./types";

export const FEED_KINDS = ["orchestra_state", "orchestra_claim", "orchestra_merge", "orchestra_gate", "orchestra_report"];
const POLL_MS = 5000;
const timers: Record<string, number> = {};

function later(name: string, ms: number, fn: () => void): void {
  window.clearTimeout(timers[name]);
  timers[name] = window.setTimeout(fn, ms);
}

function fail(e: unknown): void {
  const text = e instanceof ApiError ? e.message : String(e);
  orch.update(() => ({ error: text, loading: false }));
}

export async function loadRuns(): Promise<RunRow[]> {
  try {
    const runs = await api.get<RunRow[]>("orchestra/runs");
    orch.update(() => ({ runs, error: "" }));
    return runs;
  } catch (e) {
    fail(e);
    return [];
  }
}

export async function refresh(): Promise<void> {
  const id = orch.get().runId;
  if (!id) return;
  try {
    const data = await api.get<RunPayload>(`orchestra/${encodeURIComponent(id)}`);
    if (orch.get().runId !== id) return;
    const prev = orch.get().data;
    const landed = !!data.report && !prev?.report && !!prev;
    const files = data.goal.files || [];
    orch.update((s) => ({
      data,
      loading: false,
      error: "",
      file: s.file && files.includes(s.file) ? s.file : files[0] || "",
      doneAt: landed && data.report?.status === "finished" ? Date.now() : s.doneAt,
    }));
    if (landed) toast(`Run ${id} ${data.report!.status}`, data.report!.status === "finished" ? "done" : "error");
  } catch (e) {
    fail(e);
  }
}

export async function loadEvents(): Promise<void> {
  const { runId, next } = orch.get();
  if (!runId) return;
  try {
    const r = await api.get<{ events: RunEvent[]; next: number }>(`orchestra/${encodeURIComponent(runId)}/events`, { since: next });
    if (orch.get().runId !== runId || orch.get().next !== next) return;
    if (r.events.length) orch.update((s) => ({ events: [...s.events, ...r.events].slice(-2000), next: r.next }));
  } catch (e) {
    fail(e);
  }
}

export async function loadFile(path?: string): Promise<void> {
  const { runId, file } = orch.get();
  const rel = path || file;
  if (!runId || !rel) return;
  try {
    const view = await api.get<FileView>(`orchestra/${encodeURIComponent(runId)}/file`, { path: rel });
    if (orch.get().runId === runId) orch.update((s) => ({ files: { ...s.files, [view.path]: view } }));
  } catch (e) {
    fail(e);
  }
}

export async function openRun(id: string): Promise<void> {
  orch.update(() => ({ runId: id, data: null, events: [], next: 0, files: {}, file: "", focusLane: null, loading: true, doneAt: 0 }));
  await refresh();
  await Promise.all([loadEvents(), loadFile()]);
}

export function selectFile(path: string): void {
  orch.update(() => ({ file: path }));
  void loadFile(path);
}

function onFrame(kind: string, runId: string): void {
  orch.update(() => ({ lastFrame: Date.now() }));
  if (runId !== orch.get().runId) {
    later("runs", 300, () => void loadRuns());
    return;
  }
  later("run", 250, () => void refresh().then(loadEvents));
  if (kind === "orchestra_claim" || kind === "orchestra_merge" || kind === "orchestra_report") later("file", 400, () => void loadFile());
  if (kind === "orchestra_report") later("runs", 600, () => void loadRuns());
}

/** Start once, from the first Orchestra panel that mounts. */
export function startOrchestra(): void {
  if (orch.get().started) return;
  orch.update(() => ({ started: true, loading: true }));
  for (const kind of FEED_KINDS) {
    onEvent(kind, (f) => {
      const sid = f.session_id || "";
      const run = String((f.data as { run?: string } | null)?.run || (sid.startsWith("orchestra:") ? sid.slice(10) : ""));
      if (run) onFrame(kind, run);
    });
  }
  window.setInterval(() => {
    const s = orch.get();
    if (s.data?.live && studio.get().feed.status !== "open") void refresh().then(() => Promise.all([loadEvents(), loadFile()]));
  }, POLL_MS);
  void loadRuns().then((runs) => {
    if (runs.length && !orch.get().runId) return openRun(runs[0].run_id);
    orch.update(() => ({ loading: false }));
  });
}

// -- actions ----------------------------------------------------------------------

export type RunForm = {
  what: string;
  done_when: string;
  stop_when: string;
  workers: number;
  return_cap: number;
  test: string;
  files: string[];
  lineup: string;
  lead: string;
  worker: string;
  model: string;
};

export async function startRun(form: RunForm, dryRun: boolean): Promise<string[]> {
  try {
    const { model, ...goal } = form;
    const r = await api.post<{ run_id: string }>("orchestra/run", { ...goal, ...(model ? { model } : {}), dry_run: dryRun });
    toast(`${dryRun ? "Dry run" : "Run"} ${r.run_id} started`, "info");
    await loadRuns();
    await openRun(r.run_id);
    return [];
  } catch (e) {
    if (e instanceof ApiError) return e.problems.length ? e.problems : [e.message];
    return [String(e)];
  }
}

async function act(path: string, body: Record<string, unknown>, done: string): Promise<void> {
  const id = orch.get().runId;
  if (!id) return;
  try {
    await api.post(`orchestra/${encodeURIComponent(id)}/${path}`, body);
    toast(done, "done");
  } catch (e) {
    toast(e instanceof ApiError ? e.message : String(e), "error", 5000);
  }
  await refresh();
  await Promise.all([loadEvents(), loadFile()]);
}

export const stopRun = () => act("stop", { reason: "stopped from Studio" }, "Stop requested: the run stops at its next step");
export const releaseClaim = (key: string) => act("release", { key }, `Released ${key}`);
export const stealClaim = (key: string) => act("steal", { key }, `The lead took ${key}`);
