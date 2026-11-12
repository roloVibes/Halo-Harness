// The time axis of a replay (3.4.1.0 R1 "Time"): one session's agents, their state changes, the running cost, the
// marks (a spawn, a hand-off, an ask, a failure, a finish) and the phase bands (the 3.3.16.2 words), read from
// `GET fleet/replay` (live/timeline.py on the server) or from a saved `.halo-replay` file -- the same shape. A goal run
// or a mission has only each lane's or part's start and end: its axis is `coarse` (who existed, at work until it
// ended, how it ended). `nodesAt` draws the canvas AS IT WAS at t, `waitsAt` what each agent waited on then (so the
// narration sentence and the waiting path are rebuilt by the same narrate.ts), `talksAt` the hand-offs for the plan's
// line labels. Pure: no request, no store.
import type { LiveNode } from "../../roles/liveModel";
import type { TalkMsg } from "../../shared/liveTalk";
import type { Wait } from "./waits";

export type MarkKind = "spawn" | "handoff" | "ask" | "fail" | "finish";
export type Mark = { t: number; kind: MarkKind; agent_id: string; name: string; text: string; to?: string };
export type Band = { t0: number; t1: number; phase: "idle" | "writing" | "thinking" | "tool" | "waiting" };
export type TState = { t: number; agent_id: string; state: string; activity?: string; tool?: string };
type Point = { t: number; usd: number; agent_id?: string };
/** What `GET fleet/replay` answers and a replay file holds (the keys both share). */
export type SessionTimeline = {
  session_id: string; kind?: string; title?: string; started?: number | null; ended?: number | null; cost_usd?: number | null; harness?: string;
  agents: Record<string, unknown>[]; states?: TState[]; costs?: Point[]; agent_costs?: Point[]; marks?: Mark[]; bands?: Band[];
};
export type Timeline = { t0: number; t1: number; base: LiveNode[]; states: Map<string, TState[]>; costs: Point[]; agentCosts: Map<string, Point[]>;
  marks: Mark[]; bands: Band[]; coarse: boolean; scope: string; rows: { id: string; bio: string; lineup: string }[];
  /** 3.4.1.1 (60): a goal run's (or a mission's) record gives each agent's cost at its END only: before it, unknown. */
  endsOnly: boolean };

/** "m:ss" (or "h:mm:ss") for a number of seconds. */
export const mmss = (v: number) => {
  const s = Math.max(0, Math.round(v));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? h + ":" + String(m).padStart(2, "0") : String(m)) + ":" + String(x).padStart(2, "0");
};
const num = (v: unknown): number | null => (typeof v === "number" && isFinite(v) ? v : null);
const str = (v: unknown): string => (v == null ? "" : String(v));
export const BLANK = { key: "", pick: "", activity: "", glow: "" as const, card: "", cardLabel: "", current: "", model: "", role: "", task: "",
  cost: null, started: null, ended: null };
const LIVE = ["queued", "running", "waiting", "paused"];

function group<T extends { agent_id?: string }>(rows: T[]): Map<string, T[]> {
  const out = new Map<string, T[]>();
  for (const r of rows) out.set(str(r.agent_id), [...(out.get(str(r.agent_id)) || []), r]);
  return out;
}

/** A session's axis: `scope` keys its agents (`replay|<scope>|<agent>`), so the plan's lines know main from the rest. */
export function fromSession(m: SessionTimeline, scope: string): Timeline {
  const states = [...(m.states || [])].filter((s) => s && typeof s.t === "number").sort((a, b) => a.t - b.t);
  const ids = new Set(m.agents.map((a) => str(a.agent_id)));
  const base: LiveNode[] = m.agents.map((a) => {
    const id = str(a.agent_id), parent = str(a.parent);
    return { ...BLANK, id, key: `replay|${scope}|${id}`, parent: parent && ids.has(parent) ? parent : null, name: str(a.name || id), role: str(a.role),
             model: str(a.model), state: str(a.state || "done"), task: str(a.task), cost: num(a.cost_usd), started: num(a.since), ended: num(a.ended) };
  });
  const times = [num(m.started), num(m.ended), ...states.map((s) => s.t)].filter((t): t is number => t !== null);
  const t0 = times.length ? Math.min(...times) : 0;
  const t1 = Math.max(t0 + 1, ...times);
  return { t0, t1, base, states: group(states), costs: m.costs || [], agentCosts: group(m.agent_costs || []), marks: m.marks || [], bands: m.bands || [],
           coarse: false, scope, rows: m.agents.map((a) => ({ id: str(a.agent_id), bio: str(a.bio), lineup: str(a.lineup) })), endsOnly: m.kind === "run" };
}

/** A goal run's or a mission's axis from its nodes as they ended: each from its start to its end. */
export function fromNodes(nodes: LiveNode[], ended: number | null, scope: string): Timeline {
  const starts = nodes.map((n) => n.started).filter((t): t is number => t !== null);
  const ends = nodes.map((n) => n.ended).filter((t): t is number => t !== null);
  const t0 = starts.length ? Math.min(...starts) : (ended || Date.now() / 1000) - 60;
  const t1 = Math.max(t0 + 1, ended || 0, ...ends, ...starts);
  const marks: Mark[] = [];
  for (const n of nodes) {
    if (n.parent && n.started) marks.push({ t: n.started, kind: "spawn", agent_id: n.id, name: n.name, text: n.task, to: n.parent });
    if (n.ended && !LIVE.includes(n.state)) marks.push({ t: n.ended, kind: n.state === "failed" ? "fail" : "finish", agent_id: n.id, name: n.name, text: `${n.name} ${n.state}` });
  }
  return { t0, t1, base: nodes.map((n) => ({ ...n, key: n.key || `replay|${scope}|${n.id}` })), states: new Map(), costs: [], agentCosts: new Map(),
           marks: marks.sort((a, b) => a.t - b.t), bands: [], coarse: true, scope, rows: [], endsOnly: true };
}

function lastAt<T extends { t: number }>(rows: T[] | undefined, t: number): T | null {
  let hit: T | null = null;
  for (const r of rows || []) {
    if (r.t > t + 1e-6) break;
    hit = r;
  }
  return hit;
}

/** What it had cost at t; null where the record cannot say (an ends-only axis before its last agent ended). */
export function costAt(tl: Timeline, t: number): number | null {
  if (!tl.endsOnly) return lastAt(tl.costs, t)?.usd || 0;
  if (tl.costs.length) return t >= tl.costs[tl.costs.length - 1].t - 1e-6 ? tl.costs[tl.costs.length - 1].usd : null;
  const all = tl.base.map((n) => n.cost);
  return t >= tl.t1 - 1e-6 && all.length && all.every((c) => c !== null) ? all.reduce((s, c) => s + Number(c), 0) : null;
}

/** The canvas as it was at t: who existed, each one's state, what it ran, what it had cost. */
export function nodesAt(tl: Timeline, t: number): LiveNode[] {
  const here = tl.base.filter((n) => n.started === null || n.started <= t + 1e-6 || !n.parent);
  const ids = new Set(here.map((n) => n.id));
  return here.map((n) => {
    const s = lastAt(tl.states.get(n.id), t);
    const over = n.ended !== null && n.ended <= t + 1e-6;
    const state = s ? s.state : over || (tl.coarse && t >= tl.t1 - 1e-6) ? n.state : n.started !== null && n.started > t ? "queued" : "running";
    const current = s?.activity === "tool" ? str(s.tool) : s?.activity === "typing" ? "" : n.current && !over ? n.current : "";
    const pts = tl.agentCosts.get(n.id);
    const at = lastAt(pts, t)?.usd; // no points (a coarse axis, an older file): known at its end
    const cost = pts?.length ? at ?? (tl.endsOnly ? null : 0) : over ? n.cost : null;
    const costUnknown = tl.endsOnly && cost === null; // 3.4.1.1 (60): said "cost unknown", never $0
    return { ...n, parent: n.parent && ids.has(n.parent) ? n.parent : null, state, current, activity: str(s?.activity), cost, costUnknown,
             ended: over ? n.ended : null, glow: "" as const }; // a replay is muted: its state shows in words, never in the live glow
  });
}

/** The names of the agents at work at t (the scrubber's `data-lit`). */
export const litAt = (nodes: LiveNode[]): string[] => nodes.filter((n) => n.state === "running" || n.state === "waiting").map((n) => n.name);

const DELEGATES = ["Agent", "Task", "Workflow"];

/** What each agent waited on at t, by Live's rules (waits.ts), from the axis instead of the feed. */
export function waitsAt(tl: Timeline, nodes: LiveNode[], t: number): Map<string, Wait> {
  const out = new Map<string, Wait>();
  for (const n of nodes) {
    if (!LIVE.includes(n.state)) continue;
    const since = (lastAt(tl.states.get(n.id), t)?.t ?? n.started ?? t) * 1000;
    if (n.state === "waiting") {
      const ask = [...tl.marks].reverse().find((m) => m.kind === "ask" && m.agent_id === n.id && m.t <= t + 1e-6);
      out.set(n.id, { kind: "you", what: ask ? `${n.name} asks: ${ask.text}` : `${n.name} asks you`, since: ask ? ask.t * 1000 : since, who: n.key });
    } else if (n.state === "queued") out.set(n.id, { kind: "nothing", what: "queued, not started", since: null, who: n.key });
    else if (DELEGATES.includes(n.current)) {
      const kid = nodes.filter((k) => k.parent === n.id && LIVE.includes(k.state)).pop();
      out.set(n.id, kid ? { kind: "agent", what: kid.role && kid.role !== kid.name ? kid.role : kid.name, since, who: kid.key } : { kind: "tool", what: n.current, since, who: n.key });
    } else if (n.current) out.set(n.id, { kind: "tool", what: n.current, since, who: n.key });
    else out.set(n.id, { kind: "model", what: "a model reply", since, who: n.key });
  }
  return out;
}

/** The hand-offs up to t as the TALK messages the plan's line labels read (a spawn's task, a hand-back). */
export function talksAt(tl: Timeline, t: number): TalkMsg[] {
  const name = new Map(tl.base.map((n) => [n.id, n.name]));
  const key = (id: string) => `replay|${tl.scope}|${id}`;
  return tl.marks.filter((m) => m.t <= t + 1e-6 && m.to && (m.kind === "spawn" || m.kind === "handoff")).map((m, i) => {
    const [from, to] = m.kind === "spawn" ? [m.to!, m.agent_id] : [m.agent_id, m.to!];
    return { id: `r${i}`, from, to, why: m.kind === "spawn" ? "task" : "hand-back", fromName: name.get(from) || from, toName: name.get(to) || to,
             fromKey: key(from), toKey: key(to), text: m.text, ts: m.t, n: i };
  });
}
