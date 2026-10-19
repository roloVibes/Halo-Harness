// The Fleet section's one store (the lib/store pattern): every harness with
// its sessions and agent trees (GET fleet, then the feed: sync.ts), one
// stream per agent (streams.ts), what each agent is doing right now, the lit
// spawn edges, and the view's own choices: the selected agent (the Inspector
// and fleet-agent follow it), the pinned one (the picture-in-picture mini
// stream), follow, By project. A key is `harness|session|agent`. 3.1.4.0 R2:
// `scope` narrows the panels to one harness and session (scope.ts; Session sets it).
import { useEffect, useMemo, useState } from "react";
import { createStore, useStore, writeLocal } from "../../lib/store";
import { settle, type MotionState } from "../../lib/motion";
import { LIVE_STATES, type Activity, type AgentKey, type AgentRef, type AgentRow, type Harness, type HubInfo, type LitEdge, type SessionRow, type Stream } from "./types";

export type FleetUiView = "auto" | "start" | "workspace";
export type StreamTab = "thinking" | "working" | "output";
export type Confirm = { what: "stop" | "shutdown"; key: AgentKey; label: string } | null;
/** 3.1.4.0 R2: what the map, the activity, the attention rows and the costs show (scope.ts); {} = the whole fleet. */
export type Scope = { harness?: string; session?: string };

export type FleetState = {
  harnesses: Harness[];
  hub: HubInfo | null;
  loaded: boolean;
  error: string;
  started: boolean;
  lastFrame: number;
  selected: AgentKey;
  pinned: AgentKey;
  follow: boolean;
  byProject: boolean;
  view: FleetUiView;
  tab: StreamTab;
  columns: "tabs" | "columns";
  streams: Record<AgentKey, Stream>;
  activity: Record<AgentKey, Activity>;
  edges: LitEdge[];
  doneAt: Record<AgentKey, number>;
  /** Bumped to move the keyboard focus into the Steer box. */
  steerFocus: number;
  pairOpen: boolean;
  confirm: Confirm;
  scope: Scope;
};

const OPTS = "halo.studio.fleet.opts";

function readOpts(): Partial<FleetState> {
  try {
    const raw = JSON.parse(localStorage.getItem(OPTS) || "{}");
    return { byProject: !!raw.byProject, follow: raw.follow !== false, columns: raw.columns === "columns" ? "columns" : "tabs" };
  } catch {
    return {};
  }
}

export const fleet = createStore<FleetState>({
  harnesses: [],
  hub: null,
  loaded: false,
  error: "",
  started: false,
  lastFrame: 0,
  selected: "",
  pinned: "",
  follow: true,
  byProject: false,
  view: (/[?&]view=(start|workspace)/.exec(location.search)?.[1] as FleetUiView) || "auto",
  tab: "thinking",
  columns: "tabs",
  streams: {},
  activity: {},
  edges: [],
  doneAt: {},
  steerFocus: 0,
  pairOpen: false,
  confirm: null,
  scope: {},
  ...readOpts(),
});

export function useFleet<S>(select: (s: FleetState) => S): S {
  return useStore(fleet, select);
}

export function saveOpts(): void {
  const s = fleet.get();
  writeLocal(OPTS, JSON.stringify({ byProject: s.byProject, follow: s.follow, columns: s.columns }));
}

export const NONE: never[] = [];

// -- keys ----------------------------------------------------------------------------
export const keyOf = (h: string, s: string, a: string): AgentKey => `${h}|${s}|${a}`;

export function parseKey(key: AgentKey): { h: string; s: string; a: string } {
  const [h = "", s = "", ...rest] = key.split("|");
  return { h, s, a: rest.join("|") || "main" };
}

export function localId(s: FleetState = fleet.get()): string {
  return s.harnesses.find((h) => h.local)?.id || "";
}

// -- the tree -----------------------------------------------------------------------
/** A session's agents in tree order (each under its parent), with their depth. */
export function treeOf(rows: AgentRow[]): { a: AgentRow; depth: number }[] {
  const ids = new Set(rows.map((r) => r.agent_id));
  const kids = new Map<string, AgentRow[]>();
  for (const r of rows) {
    const p = r.parent && ids.has(r.parent) ? r.parent : "";
    if (!kids.has(p)) kids.set(p, []);
    kids.get(p)!.push(r);
  }
  const out: { a: AgentRow; depth: number }[] = [];
  const walk = (p: string, depth: number) => {
    for (const r of kids.get(p) || []) {
      out.push({ a: r, depth });
      if (depth < 8) walk(r.agent_id, depth + 1);
    }
  };
  walk("", 0);
  return out;
}

/** Every agent of every session of every harness, the local harness first, in tree order. */
export function allAgents(s: FleetState): AgentRef[] {
  const out: AgentRef[] = [];
  for (const h of s.harnesses)
    for (const ss of h.sessions || [])
      for (const { a, depth } of treeOf(ss.agents || [])) out.push({ key: keyOf(h.id, ss.session_id, a.agent_id), h, s: ss, a, depth });
  return out;
}

export const isLive = (a: AgentRow) => LIVE_STATES.includes(String(a.state || ""));

/** A session's name: its title, else what its main agent was asked, else the folder, else the id. */
export function sessionTitle(s: SessionRow): string {
  const main = (s.agents || []).find((a) => !a.parent);
  const folder = String(s.cwd || "").replace(/[\\/]+$/, "").split(/[\\/]/).pop();
  return String(s.title || main?.task || folder || s.session_id.slice(0, 8));
}

export function findAgent(s: FleetState, key: AgentKey): AgentRef | null {
  const { h, s: sid, a } = parseKey(key);
  const hh = s.harnesses.find((x) => x.id === h);
  const ss = hh?.sessions.find((x) => x.session_id === sid);
  const row = ss?.agents?.find((x) => x.agent_id === a);
  return hh && ss && row ? { key, h: hh, s: ss, a: row, depth: 0 } : null;
}

export function findSession(s: FleetState, hid: string, sid: string): { h: Harness; s: SessionRow } | null {
  const h = s.harnesses.find((x) => x.id === hid);
  const ss = h?.sessions.find((x) => x.session_id === sid);
  return h && ss ? { h, s: ss } : null;
}

export type Counts = { harnesses: number; sessions: number; agents: number; live: number; attention: number };

export function counts(s: Pick<FleetState, "harnesses">): Counts {
  let sessions = 0, agents = 0, live = 0, attention = 0;
  for (const h of s.harnesses)
    for (const ss of h.sessions || []) {
      sessions += 1;
      if (ss.status === "waiting") attention += 1;
      for (const a of ss.agents || []) {
        agents += 1;
        if (isLive(a)) live += 1;
        if (a.state === "waiting" && ss.status !== "waiting") attention += 1;
      }
    }
  return { harnesses: s.harnesses.length, sessions, agents, live, attention };
}

/** The counts, recomputed only when the tree changes (a selector must return a stable value). */
export function useCounts(): Counts {
  const harnesses = useFleet((s) => s.harnesses);
  return useMemo(() => counts({ harnesses }), [harnesses]);
}

/** The selected agent's row (null when none), stable between renders. */
export function useSelected(): AgentRef | null {
  const key = useFleet((s) => s.selected);
  const harnesses = useFleet((s) => s.harnesses);
  return useMemo(() => (key ? findAgent({ harnesses } as FleetState, key) : null), [key, harnesses]);
}

/** Now (ms), ticking every `ms` while `on` (elapsed times). */
export function useNow(on: boolean, ms = 1000): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!on) return;
    const id = window.setInterval(() => setNow(Date.now()), ms);
    return () => window.clearInterval(id);
  }, [on, ms]);
  return now;
}

/** The Start view: asked for, or only this harness is here and nothing runs on it. */
export function showsStart(s: FleetState): boolean {
  if (s.view !== "auto") return s.view === "start";
  return s.loaded && s.harnesses.length <= 1 && !s.harnesses.some((h) => (h.sessions || []).length);
}

export function setView(view: FleetUiView): void {
  fleet.update(() => ({ view }));
}

export function enterWorkspace(): void {
  fleet.update((s) => (showsStart(s) ? { view: "workspace" } : {}));
}

// -- state -> motion (lib/motion's vocabulary) --------------------------------------
export function agentMotion(a: AgentRow | undefined, doneAt = 0): MotionState {
  switch (a?.state) {
    case "running":
      return "working";
    case "waiting":
    case "paused":
      return "waiting";
    case "failed":
      return "error";
    case "done":
      return settle(doneAt, 1800);
    case "queued":
    case "stopped":
      return "idle";
    default:
      return "none";
  }
}

export function sessionMotion(ss: SessionRow): MotionState {
  if (ss.status === "waiting") return "waiting";
  if (ss.busy || ss.status === "busy" || (ss.agents || []).some((a) => a.state === "running")) return "working";
  return "idle";
}

/** The tool in flight from the row's `current` ("Bash: npm test" -> "Bash"), else from the frames. */
export function toolOf(a: AgentRow | undefined, act?: Activity): string {
  const cur = String(a?.current || "");
  if (cur && cur !== "thinking") return cur.split(":")[0].trim();
  return act?.kind === "tool" && act.tool ? act.tool : "";
}
