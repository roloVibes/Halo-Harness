// Feeds the Mission panel's store (mstore.ts) and does what its buttons
// ask: the missions list (`GET fleet/missions`, again on every `fleet` frame
// with action `mission` and every POLL_MS while the tab shows), the open
// mission (`GET fleet/missions/<id>`), Plan it (`POST fleet/missions`), Plan
// again, reassign or drop a part (`POST .../parts/<n>`), Approve, Run (it
// approves first), Stop, the report and the folder's files. Started once
// with the map's store (sync.ts startFleet), so the status bar counts the
// running missions in every section.
import { api, ApiError } from "../../lib/api";
import { onEvent } from "../../lib/events";
import { toast } from "../../lib/store";
import { showFleetPanel } from "./extras";
import { faceFor, FINAL, missions, type FileRow, type FileText, type Report, type Summary, type View } from "./mstore";

const POLL_MS = 15000;
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));
const path = (id: string, rest = "") => `fleet/missions/${encodeURIComponent(id)}${rest}`;
let pending = 0;

export async function loadMissions(): Promise<void> {
  try {
    const r = await api.get<{ missions: Summary[] }>("fleet/missions");
    missions.update(() => ({ list: r.missions || [], listError: "" }));
  } catch (e) {
    missions.update(() => ({ listError: msg(e) }));
  }
}

function took(v: View): void {
  missions.update((s) => ({ view: v, viewError: "", notHere: "", open: v.mission.id, problems: s.open === v.mission.id ? s.problems : [] }));
  if (FINAL.includes(v.mission.state)) void loadReport();
}

/** Read the open mission again (a frame, a poll, after an action). */
export async function refresh(): Promise<void> {
  const id = missions.get().open;
  if (!id) return;
  try {
    took(await api.get<View>(path(id)));
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) missions.update(() => ({ notHere: id, view: null }));
    else missions.update(() => ({ viewError: msg(e) }));
  }
}

/** Open a mission in the panel (the list's Open, an attention row's O, the rail). */
export function openMission(id: string, part = "", show = true): void {
  missions.update((s) => ({ open: id, view: s.view?.mission.id === id ? s.view : null, face: "auto", selPart: part, report: null, files: null, problems: [], drag: null }));
  if (show) showFleetPanel("fleet-mission");
  void refresh();
}

export function closeMission(): void {
  missions.update(() => ({ open: "", view: null, face: "start", selPart: "", report: null, files: null, problems: [], drag: null, notHere: "" }));
  void loadMissions();
}

/** The palette's "Fleet: new mission": the Start face with the goal box focused. */
export function newMission(): void {
  closeMission();
  showFleetPanel("fleet-mission");
  missions.update((s) => ({ newFocus: s.newFocus + 1 }));
}

async function act(label: string, run: () => Promise<View>, done = ""): Promise<boolean> {
  missions.update(() => ({ busy: label, problems: [] }));
  try {
    const v = await run();
    took(v);
    missions.update(() => ({ face: "auto" }));
    if (done) toast(done, "done");
    void loadMissions();
    return true;
  } catch (e) {
    const problems = e instanceof ApiError ? e.problems.filter((p) => p.length > 12) : [];
    missions.update(() => ({ problems: problems.length ? problems : [msg(e)] }));
    if (e instanceof ApiError && e.data?.id && e.data?.mission) took(e.data as unknown as View);
    toast(msg(e), "error", 6000);
    return false;
  } finally {
    missions.update(() => ({ busy: "" }));
  }
}

export type NewBody = { goal: string; constraints: string; prefer: string[]; budget_usd: string };

export function planIt(b: NewBody): Promise<boolean> {
  const body = { goal: b.goal.trim(), constraints: b.constraints.trim(), prefer: b.prefer, ...(b.budget_usd.trim() ? { budget_usd: b.budget_usd.trim() } : {}) };
  return act("plan", () => api.post<View>("fleet/missions", body), "Planned: check the parts on the map, then Approve or Run");
}

export const planAgain = () => act("plan", () => api.post<View>(path(missions.get().open, "/plan")), "Planned again");
export const approve = () => act("approve", () => api.post<View>(path(missions.get().open, "/approve")), "Approved: Run starts it");
export const runIt = () => act("run", () => api.post<View>(path(missions.get().open, "/run")), "Running: the parts start by their dependencies");
export const dropPart = (pid: string) => act("drop", () => api.post<View>(path(missions.get().open, `/parts/${pid}`), { drop: true }), `Part ${pid} dropped`);

export async function stopIt(reason: string): Promise<boolean> {
  missions.update(() => ({ stopAsk: false }));
  return act("stop", () => api.post<View>(path(missions.get().open, "/stop"), { reason }), "Stopped: every running part was asked to stop");
}

/** Drag a part node to another harness box: the route checks it in code; a 422 snaps it back with the reason. */
export async function reassign(pid: string, harness: string, name: string): Promise<boolean> {
  const id = missions.get().open;
  missions.update((s) => ({ drag: s.drag ? { ...s.drag, pending: true } : null, busy: "edit" }));
  try {
    took(await api.post<View>(path(id, `/parts/${pid}`), { harness }));
    toast(`Part ${pid} now runs on ${name}`, "done");
    return true;
  } catch (e) {
    toast(`Part ${pid} stays: ${msg(e)}`, "error", 6000);
    return false;
  } finally {
    missions.update(() => ({ drag: null, busy: "" }));
  }
}

export async function loadReport(): Promise<void> {
  const id = missions.get().open;
  if (!id) return;
  try {
    const [r, f] = await Promise.all([
      api.get<{ report: Report; markdown: string; final: boolean }>(path(id, "/report")),
      api.get<{ files: FileRow[] }>(path(id, "/files")).catch(() => ({ files: [] as FileRow[] })),
    ]);
    if (missions.get().open === id) missions.update(() => ({ report: r, reportError: "", files: f.files || [] }));
  } catch (e) {
    missions.update(() => ({ reportError: msg(e) }));
  }
}

/** An artifact or a hand-back: a text file opens in the viewer; a binary says its size. */
export async function openFile(rel: string): Promise<void> {
  const id = missions.get().open;
  try {
    const r = await api.get<FileText>(path(id, "/files"), { path: rel });
    missions.update(() => ({ file: r }));
  } catch (e) {
    const size = e instanceof ApiError ? Number(e.data?.size) : NaN;
    if (e instanceof ApiError && e.status === 415) toast(`${rel} is a binary file (${Number.isFinite(size) ? Math.max(1, Math.round(size / 1024)) + " KB" : "size unknown"}): open it from the mission folder`, "info", 5000);
    else toast(msg(e), "error", 5000);
  }
}

export const closeFile = () => missions.update(() => ({ file: null }));
export const setFace = (face: "start" | "plan" | "run" | "report" | "coach") => {
  missions.update(() => ({ face }));
  if (face === "report") void loadReport();
};

/** The face the panel shows now. */
export function shownFace(s = missions.get()): "start" | "plan" | "run" | "report" | "coach" {
  if (!s.open) return "start";
  if (s.face !== "auto" && s.face !== "start") return s.face;
  return faceFor(s.view?.mission.state);
}

/** Start once: the first read, the `mission` frames, the poll while the tab shows. */
export function startMissions(): void {
  if (missions.get().started) return;
  missions.update(() => ({ started: true }));
  onEvent("fleet", (f) => {
    const d = (f.data || {}) as { action?: string; id?: string };
    if (d.action !== "mission") return;
    window.clearTimeout(pending);
    pending = window.setTimeout(() => {
      void loadMissions();
      if (d.id && d.id === missions.get().open) void refresh();
    }, 150);
  });
  window.setInterval(() => {
    if (document.hidden) return;
    void loadMissions();
    const v = missions.get().view;
    if (v && !FINAL.includes(v.mission.state)) void refresh();
  }, POLL_MS);
  void loadMissions();
}
