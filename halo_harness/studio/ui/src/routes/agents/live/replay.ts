// A replay on Live (3.3.18.0 "The living canvas"; 3.4.1.0 R1 "Time": with time): something past -- a session, a goal
// run, a mission, a saved `.halo-replay` file -- or the session drawn now, rewound, on Live's canvas AS IT WAS at the
// scrubber's moment (timeline.ts nodesAt), muted, under a "replay -- <time>" banner. The scrubber under the canvas
// (Scrubber.tsx) is the ONE replay control: drag, Play at 1x / 4x / 16x, Now. Opened from History's rows, a goal run's
// report (Replay), a file chosen in History, `?replay=<id>` (`halo replay open`), the empty state's "Replay the last
// session", the agent inspector's history and the palette. Nothing past reaches the canvas any other way. None of its
// nodes is a live agent (keys `replay|...`): no glow, no steer, no inspector.
import { api, ApiError } from "../../../lib/api";
import { createStore, goSection, toast, useStore } from "../../../lib/store";
import { partState, type View } from "../../fleet/mstore";
import type { RunPayload } from "../../orchestra/types";
import type { LiveNode } from "../../roles/liveModel";
import { runNodes } from "./runLanes";
import type { Plan } from "./planStore";
import { BLANK, fromNodes, fromSession, nodesAt, type SessionTimeline, type Timeline } from "./timeline";

export type HistoryKind = "session" | "run" | "mission" | "file";
/** A saved replay file's payload (live/replay_file.py, format halo-replay version 1). */
export type ReplayFile = SessionTimeline & { format: string; version: number; id: string; saved: number | null; plan: Plan | null; includes?: string[] };
export type LiveReplay = {
  kind: HistoryKind; id: string; title: string; ended: number | null; tl: Timeline; t: number; playing: boolean; speed: number;
  /** the session behind it (what Save writes; "" for a run or a mission), and whether it is the one running now */
  sid: string; live: boolean; plan: Plan | null; nodes: LiveNode[];
};

export const SPEEDS = [1, 4, 16];
export const liveReplay = createStore<{ r: LiveReplay | null; busy: string }>({ r: null, busy: "" });
export const useLiveReplay = (): LiveReplay | null => useStore(liveReplay, (s) => s.r);
const TICK_MS = 100;
let timer = 0;

const num = (v: unknown): number | null => (typeof v === "number" && isFinite(v) ? v : null);
const str = (v: unknown): string => (v == null ? "" : String(v));

/** A run's lead and lanes as they ended. */
export function runReplayNodes(data: RunPayload): LiveNode[] {
  return runNodes({ ...data, live: true }).map((n) => ({ ...n, glow: "" as const, state: n.id.includes(":lane:") ? n.state : str(data.run.state) }));
}

/** A mission's parts as they ended, under one node for the mission. */
export function missionNodes(v: View): LiveNode[] {
  const root = `mission:${v.mission.id}`;
  const out: LiveNode[] = [{ ...BLANK, id: root, parent: null, name: "mission", role: "mission", state: str(v.mission.state), task: str(v.summary?.goal),
                             cost: num(v.summary?.cost_usd), started: num(v.summary?.created), ended: num(v.summary?.ended) }];
  for (const p of v.plan?.parts || []) {
    const run = v.mission.parts?.[p.id];
    out.push({ ...BLANK, id: `${root}:${p.id}`, parent: root, name: str(p.title), role: str(p.kind), state: partState(v, p.id), task: str(p.brief),
               cost: num(run?.cost_usd), started: num(run?.started), ended: num(run?.ended) });
  }
  return out;
}

function put(r: Omit<LiveReplay, "nodes" | "playing" | "speed" | "t">, at: number | null): void {
  window.clearInterval(timer);
  const t = Math.max(r.tl.t0, Math.min(r.tl.t1, at ?? r.tl.t1));
  liveReplay.update(() => ({ r: { ...r, t, playing: false, speed: 4, nodes: nodesAt(r.tl, t) } }));
}

/** Open a past thing (or the session drawn now, `live`) as a replay on Live, at `at` (epoch s; default: its end). */
export async function openLiveReplay(kind: HistoryKind, id: string, title: string, at: number | null = null, live = false): Promise<boolean> {
  if (kind === "file") return openFileReplay(id, at);
  liveReplay.update(() => ({ busy: `${kind}:${id}` }));
  try {
    let tl: Timeline, ended: number | null;
    if (kind === "session") {
      const meta = await api.get<SessionTimeline>("fleet/replay", { session: id, harness: "local" });
      tl = fromSession(meta, id);
      ended = num(meta.ended);
      title = meta.title || title; // the session's own title over the row's words
    } else if (kind === "run") {
      const data = await api.get<RunPayload>(`orchestra/${encodeURIComponent(id)}`);
      ended = num(data.report?.ts) ?? num(data.run.created);
      tl = fromNodes(runReplayNodes(data), ended, id);
    } else {
      const v = await api.get<View>(`fleet/missions/${encodeURIComponent(id)}`);
      ended = num(v.summary?.ended) ?? num(v.summary?.updated);
      tl = fromNodes(missionNodes(v), ended, id);
    }
    if (!tl.base.length) {
      toast("Nothing to replay: it left no agents", "info", 4000);
      return false;
    }
    put({ kind, id, title, ended, tl, sid: kind === "session" ? id : "", live, plan: null }, at);
    return true;
  } catch (e) {
    toast(`No replay: ${e instanceof ApiError ? e.message : String(e)}`, "error", 5000);
    return false;
  } finally {
    liveReplay.update(() => ({ busy: "" }));
  }
}

/** A saved replay file (`<state>/replays/<id>.halo-replay`) on Live. */
export async function openFileReplay(rid: string, at: number | null = null): Promise<boolean> {
  liveReplay.update(() => ({ busy: `file:${rid}` }));
  try {
    const f = await api.get<ReplayFile>(`replays/${encodeURIComponent(rid)}`);
    const tl = fromSession(f, rid);
    if (!tl.base.length) {
      toast("Nothing to replay: the file holds no agents", "info", 4000);
      return false;
    }
    put({ kind: "file", id: rid, title: f.title || f.session_id, ended: num(f.ended), tl, sid: "", live: false, plan: f.plan || null }, at);
    return true;
  } catch (e) {
    toast(`No replay: ${e instanceof ApiError ? e.message : String(e)}`, "error", 5000);
    return false;
  } finally {
    liveReplay.update(() => ({ busy: "" }));
  }
}

/** A session played back from the agent inspector, the Roles Live tab's history or the palette: on Live. */
export function replaySession(sid: string, title = ""): Promise<boolean> {
  goSection("agents", "live");
  return openLiveReplay("session", sid, title || `session ${sid.slice(0, 8)}`);
}

function patch(fn: (r: LiveReplay) => Partial<LiveReplay>): void {
  liveReplay.update((s) => {
    if (!s.r) return {};
    const r = { ...s.r, ...fn(s.r) };
    return { r: r.t === s.r.t ? r : { ...r, nodes: nodesAt(r.tl, r.t) } };
  });
}

/** The scrub: to `t` (epoch s); it pauses the playback. */
export function scrubTo(t: number): void {
  window.clearInterval(timer);
  patch((r) => ({ playing: false, t: Math.max(r.tl.t0, Math.min(r.tl.t1, t)) }));
}

/** Play forward at the replay's speed from where it stands (from the start when it stands at the end). */
export function play(on: boolean): void {
  window.clearInterval(timer);
  patch((r) => ({ playing: on, t: on && r.t >= r.tl.t1 - 1e-6 ? r.tl.t0 : r.t }));
  if (!on) return;
  timer = window.setInterval(() => {
    const r = liveReplay.get().r;
    if (!r || !r.playing) return window.clearInterval(timer);
    const t = Math.min(r.tl.t1, r.t + (TICK_MS / 1000) * r.speed);
    patch(() => ({ t, playing: t < r.tl.t1 }));
    if (t >= r.tl.t1) window.clearInterval(timer);
  }, TICK_MS);
}

export const setSpeed = (speed: number) => patch(() => ({ speed: SPEEDS.includes(speed) ? speed : 4 }));

let doorDone = false;
/** `?replay=<id>[&at=<seconds since its start>]` (`halo replay open`, the clip's filming): that saved file, once a page. */
export function replayDoor(): void {
  if (doorDone) return;
  doorDone = true;
  try {
    const q = new URLSearchParams(location.search);
    const rid = q.get("replay"), at = Number(q.get("at"));
    if (rid && /^[A-Za-z0-9_.-]{1,120}$/.test(rid)) void openFileReplay(rid).then((ok) => ok && q.get("at") && scrubTo((liveReplay.get().r?.tl.t0 || 0) + at));
  } catch {
    /* no door */
  }
}

/** Now: the replay leaves the canvas, Live draws what runs. */
export function backToNow(): void {
  window.clearInterval(timer);
  liveReplay.update((s) => (s.r ? { r: null } : {}));
}
