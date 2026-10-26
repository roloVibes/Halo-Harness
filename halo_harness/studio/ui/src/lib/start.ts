// "Start here" (3.1.1.0 R1): on a fresh home (no lineup of your own, no run)
// Studio offers the guided first run. GET /api/start says whether to show
// the overlay and carries the seven steps' titles, the running job and
// (3.2.2.0 R2) `card`, the lines `halo start` opens on: what it does, the
// models it will call, the estimated cost, the time and what it writes;
// POST /api/start runs `halo start --yes` as a background job whose steps
// arrive as `start` frames on the live feed (polled from GET /api/start too,
// so a closed feed still shows them); POST /api/start/dismiss is "Just look
// around", remembered for the home. `?tour=off` (captures, tests) keeps the
// overlay shut, like the first-visit welcome.
import { ApiError, api } from "./api";
import { onEvent } from "./events";
import { createStore, studio, welcomeIfNew } from "./store";

export type StartFrame = {
  step: number;
  total?: number;
  key: string;
  title: string;
  why: string;
  command?: string;
  state: string;
  lines?: string[];
};
export type StartSummary = { ok?: boolean; stopped_at?: string | null; reason?: string; error_log?: string; lineup?: string; repo?: string; run?: string; coach?: number; message?: string };
type Job = { job: string; running: boolean; fake?: boolean; steps: StartFrame[]; summary: StartSummary | null };
type Status = { show: boolean; fresh: boolean; plan: StartFrame[]; job: Job | null; card?: string[] };

type StartState = {
  open: boolean;
  view: "offer" | "run";
  plan: StartFrame[];
  card: string[];
  steps: Record<string, StartFrame>;
  summary: StartSummary | null;
  running: boolean;
  error: string;
  busy: boolean;
};

export const start = createStore<StartState>({ open: false, view: "offer", plan: [], card: [], steps: {}, summary: null, running: false, error: "", busy: false });

// 3.1.1.0 R3: a page opened on an edit (`?edit=`, `halo studio --edit`) goes straight to it, no overlay.
const QUIET = typeof location !== "undefined" && /[?&]((tour|start)=off\b|edit=)/.test(location.search);
let fed = false;
let timer = 0;

function adoptJob(job: Job | null): void {
  if (!job) return;
  const steps: Record<string, StartFrame> = {};
  for (const f of job.steps || []) steps[f.key] = f;
  start.update((s) => ({ steps: { ...s.steps, ...steps }, summary: job.summary ?? s.summary, running: job.running }));
}

function feed(): void {
  if (fed) return;
  fed = true;
  onEvent("start", (f) => {
    const d = (f.data || {}) as Record<string, unknown>;
    if (d.key === "summary") {
      start.update(() => ({ summary: (d.summary as StartSummary) || {}, running: false }));
      void refresh(); // 3.2.2.0: a step's last frame can fall off the feed (the run step floods it); the server's view is final
      return;
    }
    if (typeof d.key === "string") {
      const frame = d as unknown as StartFrame;
      start.update((s) => ({ steps: { ...s.steps, [frame.key]: frame }, running: s.summary ? false : true }));
    }
  });
  onEvent("dropped", () => void refresh()); // frames fell off this browser's queue: re-read the job
}

/** One GET start, the job's latest frame per step adopted (after the summary, after a drop). */
async function refresh(): Promise<void> {
  try {
    const st = await api.get<Status>("start");
    adoptJob(st.job);
  } catch {
    /* the next frame or poll tries again */
  }
}

function poll(): void {
  window.clearTimeout(timer);
  timer = window.setTimeout(async () => {
    try {
      const st = await api.get<Status>("start");
      adoptJob(st.job);
    } catch {
      /* the next poll tries again */
    }
    if (start.get().open && start.get().view === "run" && !start.get().summary) poll();
  }, 1200);
}

/** On load: the overlay when the home is fresh (or a start is already running). */
export async function loadStart(): Promise<void> {
  feed();
  if (QUIET) return;
  try {
    const st = await api.get<Status>("start");
    start.update(() => ({ plan: st.plan || [], card: st.card || [] }));
    if (st.job && st.job.running) {
      adoptJob(st.job);
      start.update(() => ({ open: true, view: "run" }));
      poll();
    } else if (st.show) {
      const help = studio.get().help;
      if (help?.welcome) studio.update(() => ({ help: null })); // the welcome waits until Start here is answered
      start.update(() => ({ open: true, view: "offer" }));
    }
  } catch {
    /* an older Studio without the route: no overlay */
  }
}

export async function runStart(): Promise<void> {
  start.update(() => ({ busy: true, error: "", steps: {}, summary: null }));
  try {
    const r = await api.post<{ job: Job }>("start");
    adoptJob(r.job);
    start.update(() => ({ view: "run", running: true }));
    poll();
  } catch (e) {
    start.update(() => ({ error: e instanceof ApiError ? e.message : String(e) }));
  } finally {
    start.update(() => ({ busy: false }));
  }
}

export async function dismissStart(): Promise<void> {
  start.update(() => ({ open: false }));
  try {
    await api.post("start/dismiss");
  } catch {
    /* not remembered this time: it asks again on the next load */
  }
  welcomeIfNew(studio.get().section);
}

export async function stopStart(): Promise<void> {
  try {
    await api.post("start/stop");
  } catch {
    /* the poll shows what happened */
  }
}

export function closeStart(): void {
  window.clearTimeout(timer);
  start.update(() => ({ open: false }));
  welcomeIfNew(studio.get().section);
}

/** The palette's "Start: the guided first run": the overlay whatever the home (a run in progress shows its steps). */
export function openStart(): void {
  feed();
  start.update((s) => ({ open: true, view: s.running || s.summary ? "run" : "offer" }));
  if (start.get().view === "run" && !start.get().summary) poll();
  if (!start.get().plan.length || !start.get().card.length)
    api
      .get<Status>("start")
      .then((st) => start.update(() => ({ plan: st.plan || [], card: st.card || [] })))
      .catch(() => undefined);
}
