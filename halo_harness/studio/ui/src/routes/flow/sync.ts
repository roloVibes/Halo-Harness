// Feeds the Flow store: `GET flow/templates`, `GET flow/runs` and `GET
// flow/runs/<id>` on load (the newest run opens, or `?run=<id>`), then the
// live feed's `flow_*` frames: a frame of the open run refetches the payload
// and the log (debounced), a frame of another run refreshes the run list.
// `subagent_*` frames of the run's session (`flow:<run>`) are the org's live
// positions. Polling (5 s) only while the feed is not open and the run is live.
import { api, ApiError } from "../../lib/api";
import { onEvent, type FeedFrame } from "../../lib/events";
import { studio, toast } from "../../lib/store";
import { flow } from "./store";
import type { FlowEvent, FlowPayload, FlowRunRow, TemplateRow } from "./types";

export const FEED_KINDS = ["flow_state", "flow_step", "flow_gate", "flow_post", "flow_metric", "flow_report"];
const AGENT_KINDS = ["subagent_start", "subagent_progress", "subagent_end", "subagent_queued"];
const POLL_MS = 5000;
const timers: Record<string, number> = {};

export function later(name: string, ms: number, fn: () => void): void {
  window.clearTimeout(timers[name]);
  timers[name] = window.setTimeout(fn, ms);
}

export function errorText(e: unknown): string {
  return e instanceof ApiError ? e.message : String(e);
}

function fail(e: unknown): void {
  flow.update(() => ({ error: errorText(e), loading: false }));
}

export const runPath = (id: string, rest = "") => `flow/runs/${encodeURIComponent(id)}${rest}`;

export async function loadTemplates(): Promise<void> {
  try {
    const templates = await api.get<TemplateRow[]>("flow/templates");
    flow.update(() => ({ templates }));
  } catch (e) {
    fail(e);
  }
}

export async function loadRuns(): Promise<FlowRunRow[]> {
  try {
    const runs = await api.get<FlowRunRow[]>("flow/runs");
    flow.update(() => ({ runs, error: "" }));
    return runs;
  } catch (e) {
    fail(e);
    return [];
  }
}

export async function refresh(): Promise<void> {
  const id = flow.get().runId;
  if (!id) return;
  try {
    const data = await api.get<FlowPayload>(runPath(id));
    if (flow.get().runId !== id) return;
    const prev = flow.get().data;
    const landed = !!data.report && !!prev && !prev.report;
    flow.update((s) => ({
      data,
      loading: false,
      error: "",
      doneAt: landed && data.report?.status === "finished" ? Date.now() : s.doneAt,
    }));
    if (landed) toast(`Flow ${id} ${data.report!.status}`, data.report!.status === "finished" ? "done" : "error");
  } catch (e) {
    fail(e);
  }
}

export async function loadEvents(): Promise<void> {
  const { runId, next } = flow.get();
  if (!runId) return;
  try {
    const r = await api.get<{ events: FlowEvent[]; next: number }>(runPath(runId, "/events"), { since: next });
    if (flow.get().runId !== runId || flow.get().next !== next) return;
    if (r.events.length) flow.update((s) => ({ events: [...s.events, ...r.events].slice(-2000), next: r.next }));
  } catch (e) {
    fail(e);
  }
}

/** Open a run (its panels come up); `quiet` (the first load) leaves the Start view as it is. */
export async function openRun(id: string, quiet = false): Promise<void> {
  flow.update(() => ({ runId: id, data: null, events: [], next: 0, step: "", positions: {}, loading: true, doneAt: 0, ...(quiet ? {} : { view: "auto" as const }) }));
  await refresh();
  await loadEvents();
}

function onFrame(kind: string, run: string): void {
  flow.update(() => ({ lastFrame: Date.now() }));
  if (run !== flow.get().runId) {
    later("runs", 300, () => void loadRuns());
    return;
  }
  later("run", 250, () => void refresh().then(loadEvents));
  if (kind === "flow_report" || kind === "flow_state") later("runs", 600, () => void loadRuns());
}

function onAgent(f: FeedFrame): void {
  const run = (f.session_id || "").startsWith("flow:") ? f.session_id!.slice(5) : "";
  if (!run || run !== flow.get().runId) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const name = String(d.position || d.name || d.description || d.agent || f.agent_id || "agent");
  const state = f.event === "subagent_end" ? (d.is_error ? "failed" : "done") : f.event === "subagent_queued" ? "queued" : "running";
  flow.update((s) => ({ positions: { ...s.positions, [name]: state }, lastFrame: Date.now() }));
}

/** Start once, from the first Flow panel that mounts. */
export function startFlow(): void {
  if (flow.get().started) return;
  flow.update(() => ({ started: true, loading: true }));
  for (const kind of FEED_KINDS) {
    onEvent(kind, (f) => {
      const sid = f.session_id || "";
      const run = String((f.data as { run?: string } | null)?.run || (sid.startsWith("flow:") ? sid.slice(5) : ""));
      if (run) onFrame(kind, run);
    });
  }
  for (const kind of AGENT_KINDS) onEvent(kind, onAgent);
  window.setInterval(() => {
    const s = flow.get();
    if (s.data?.live && studio.get().feed.status !== "open") void refresh().then(loadEvents);
  }, POLL_MS);
  void loadTemplates();
  const asked = /[?&]run=([A-Za-z0-9_-]+)/.exec(location.search)?.[1];
  void loadRuns().then((runs) => {
    const pick = runs.find((r) => r.run === asked) || runs[0];
    if (pick && !flow.get().runId) return openRun(pick.run, true);
    flow.update(() => ({ loading: false }));
  });
}
