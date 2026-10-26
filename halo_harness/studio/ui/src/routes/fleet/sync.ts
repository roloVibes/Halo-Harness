// Feeds the Fleet store: `GET fleet` on load, then the live feed keyed by
// harness + session_id + agent_id: `agent_state` updates a row in place (a
// new child lights its spawn edge for a few seconds), `agent_event` and the
// raw `text_chunk` / `tool_use_start` / `tool_result` frames feed the
// agent's stream (streams.ts), `fleet` frames (a member's `sessions`, join,
// leave, online, offline; a local register / update / unregister) and the
// local `sessions` frame refresh the tree. Remote session lists arrive as
// `fleet` frames with action `sessions`, never as `sessions` frames (R2).
// Polling (POLL_MS) only while the feed is not open. Started once, by the
// rail (every section shows it) or the first Fleet panel. 3.1.5.0 R3: a GET
// answer never undoes a newer agent_state frame (fresh.ts). 3.1.8.0 R6: a
// session's own `message_end` and `status` frames move its figures (spend,
// tokens, turns, context, model, busy: figures.ts) on the event the terminal's
// status bar moves on, a GET never pulls them back (fresh.ts), an older GET
// answer never lands after a newer one, and an agent leaving `waiting` reads
// GET fleet again at once so the session's waiting state clears. 3.3.0.0 R7
// (a slow box): a frame that ends an agent (stopped / done / failed), or one
// that moves an ended agent again, re-reads the view at once; while anything
// runs the view is re-read every FLOOR_MS whatever frames come; a tab shown
// again re-reads it.
import { api, ApiError } from "../../lib/api";
import { onEvent, onFeedState, type FeedFrame } from "../../lib/events";
import { studio, toast } from "../../lib/store";
import { startCaps } from "./caps";
import { startMissions } from "./mload";
import { startPanels } from "./pload";
import { agentWith, FIGURE_KINDS, figuresOf, ownFrame, withFigures } from "./figures";
import { keepFresh, noteFigures, noteFrame } from "./fresh";
import { append, rawEntry } from "./streams";
import { fleet, keyOf, localId, type FleetState } from "./store";
import type { AgentRow, FleetView, Harness, SessionRow } from "./types";

const POLL_MS = 4000; // the feed is not open: the view every 4 s
export const FLOOR_MS = 5000; // 3.3.0.0 R7: the feed open and anything running: the view at least every 5 s
const TICK_MS = 500;
const ENDS = new Set(["done", "failed", "stopped"]);
const RELOAD = ["permission_request", "question", "plan_review", "approval_request", "turn_done", "subagent_start", "subagent_end"];
const RAW = ["text_chunk", "tool_use_start", "tool_result"];
const timers: Record<string, number> = {};

function later(name: string, ms: number, fn: () => void): void {
  window.clearTimeout(timers[name]);
  timers[name] = window.setTimeout(fn, ms);
}

/** Note every agent that just finished (the done sweep) between two trees. */
function finished(prev: Harness[], next: Harness[]): Record<string, number> {
  const was = new Map<string, string>();
  for (const h of prev) for (const s of h.sessions || []) for (const a of s.agents || []) was.set(keyOf(h.id, s.session_id, a.agent_id), String(a.state));
  const out: Record<string, number> = {};
  const now = Date.now();
  for (const h of next)
    for (const s of h.sessions || [])
      for (const a of s.agents || []) {
        const k = keyOf(h.id, s.session_id, a.agent_id);
        const before = was.get(k);
        if (before && before !== a.state && (a.state === "done" || a.state === "failed")) out[k] = now;
      }
  return out;
}

let asks = 0;
let landed = 0;
let lastAsk = 0;

export async function load(): Promise<void> {
  const asked = Date.now();
  lastAsk = asked;
  const mine = ++asks;
  try {
    const v = await api.get<FleetView>("fleet");
    if (mine < landed) return; // a newer answer already landed: this older one never undoes it
    landed = mine;
    const got = Array.isArray(v.harnesses) ? v.harnesses.map((h) => ({ ...h, sessions: h.sessions || [] })) : [];
    fleet.update((s) => {
      const harnesses = keepFresh(s.harnesses, got, asked);
      return { harnesses, hub: v.hub || null, loaded: true, error: "", doneAt: { ...s.doneAt, ...finished(s.harnesses, harnesses) } };
    });
  } catch (e) {
    if (mine < landed) return;
    fleet.update(() => ({ loaded: true, error: e instanceof ApiError ? e.message : String(e) }));
  }
}

function hid(f: FeedFrame, s: FleetState): string {
  return String(f.harness || localId(s) || "");
}

/** Replace one session's row (or one harness's sessions) without refetching everything. */
function mapSession(s: FleetState, h: string, sid: string, fn: (ss: SessionRow) => SessionRow): Harness[] | null {
  let hit = false;
  const harnesses = s.harnesses.map((x) => {
    if (x.id !== h) return x;
    return { ...x, sessions: x.sessions.map((ss) => (ss.session_id === sid ? ((hit = true), fn(ss)) : ss)) };
  });
  return hit ? harnesses : null;
}

function onAgentState(f: FeedFrame): void {
  const row = f.data as AgentRow | null;
  const s = fleet.get();
  const h = hid(f, s);
  const sid = String(f.session_id || "");
  if (!row || !row.agent_id || !sid) return;
  const key = keyOf(h, sid, row.agent_id);
  noteFrame(key);
  let isNew = false;
  let before = "";
  const harnesses = mapSession(s, h, sid, (ss) => {
    const list = ss.agents || [];
    const old = list.find((a) => a.agent_id === row.agent_id);
    isNew = !old;
    before = String(old?.state || "");
    return { ...ss, agents: old ? list.map((a) => (a.agent_id === row.agent_id ? agentWith(a, row) : a)) : [...list, row] };
  });
  if (!harnesses) {
    later("load", 300, () => void load());
    return;
  }
  const now = Date.now();
  const ended = before && before !== row.state && (row.state === "done" || row.state === "failed");
  // answered (the session's waiting clears), or an agent's end (3.2.3.0: its parent's and the hub's rows move too; 3.3.0.0
  // R7: from any state), or a frame that moves an ended agent again (a late frame: the view says which is true)
  if (before && before !== row.state && (before === "waiting" || ENDS.has(String(row.state)) || ENDS.has(before))) later("load", 300, () => void load());
  fleet.update((st) => ({
    harnesses,
    lastFrame: now,
    doneAt: ended ? { ...st.doneAt, [key]: now } : st.doneAt,
    edges: isNew && row.parent ? [...st.edges.filter((e) => now - e.ts < 6000), { from: keyOf(h, sid, row.parent), to: key, ts: now, kind: "spawn" }] : st.edges,
  }));
}

/** The session's own figures, from the frame its terminal's status bar moves on (figures.ts). */
function onFigures(f: FeedFrame): void {
  const sid = String(f.session_id || "");
  if (!sid || !ownFrame(f)) return;
  const fig = figuresOf(f);
  if (!Object.keys(fig).length) return;
  const s = fleet.get();
  const h = hid(f, s);
  const harnesses = mapSession(s, h, sid, (ss) => withFigures(ss, fig));
  if (!harnesses) {
    later("load", 300, () => void load());
    return;
  }
  noteFigures(h, sid, fig.busy);
  fleet.update(() => ({ harnesses, lastFrame: Date.now() }));
}

function onSessions(f: FeedFrame): void {
  const d = (f.data || {}) as { action?: string; sessions?: SessionRow[]; state?: string; error?: string; cmd?: string };
  const s = fleet.get();
  if (d.action === "attention") return; // the watcher's count (session_id null): the panels' store reads it (pload.ts)
  if (d.action === "capabilities") return; // 3.0.6.0 R6: a catalog changed; caps.ts refetches the catalogs
  if (d.action === "mission") return; // 3.0.6.0 R8: a mission moved; mload.ts reads it (its sessions come as sessions frames)
  if (d.action === "sessions" && Array.isArray(d.sessions) && f.harness && s.harnesses.some((h) => h.id === f.harness)) {
    fleet.update((st) => ({ harnesses: st.harnesses.map((h) => (h.id === f.harness ? { ...h, sessions: d.sessions! } : h)), lastFrame: Date.now() }));
    return;
  }
  if (d.action === "command" && (d.state === "refused" || d.state === "error")) toast(`${d.cmd || "command"}: ${d.error || d.state}`, "error", 5000);
  later("load", d.action === "command" ? 800 : 350, () => void load());
}

/** Who sent another agent a message (SendMessage): that edge lights too (D13). */
function messageEdge(h: string, sid: string, from: string, input: unknown): void {
  const to = input && typeof input === "object" ? String((input as Record<string, unknown>).to || (input as Record<string, unknown>).agent_id || "") : "";
  if (!to) return;
  const ss = fleet.get().harnesses.find((x) => x.id === h)?.sessions.find((x) => x.session_id === sid);
  const target = ss?.agents?.find((a) => a.agent_id === to || a.name === to || a.role === to);
  if (target) fleet.update((st) => ({ edges: [...st.edges, { from: keyOf(h, sid, from), to: keyOf(h, sid, target.agent_id), ts: Date.now(), kind: "message" }] }));
}

function onAgentEvent(f: FeedFrame): void {
  const e = f.data as Record<string, unknown> | null;
  if (!e || typeof e.kind !== "string") return;
  const s = fleet.get();
  const h = hid(f, s);
  const sid = String(f.session_id || "");
  const aid = String(f.agent_id || "main");
  const key = keyOf(h, sid, aid);
  fleet.update((st) => ({ streams: { ...st.streams, [key]: { ...(st.streams[key] || { entries: [], loaded: false, loading: false, error: "", following: true, tick: 0 }), viaEvents: true } } }));
  append(key, e as { kind: string });
  noteActivity(key, e.kind === "tool_call" ? "tool" : e.kind === "text" || e.kind === "thinking" ? "typing" : "", String(e.name || ""));
  if (e.kind === "tool_call" && /^(SendMessage|send_message|Message)$/.test(String(e.name))) messageEdge(h, sid, aid, e.input);
}

function noteActivity(key: string, kind: "typing" | "tool" | "", tool: string): void {
  if (!kind) return;
  fleet.update((st) => {
    const cur = st.activity[key];
    return { activity: { ...st.activity, [key]: { kind, tool: kind === "tool" ? tool : cur?.tool, ts: Date.now(), calls: (cur?.calls || 0) + (kind === "tool" ? 1 : 0) } } };
  });
}

function onRaw(f: FeedFrame): void {
  const s = fleet.get();
  const key = keyOf(hid(f, s), String(f.session_id || ""), String(f.agent_id || "main"));
  const e = rawEntry(f.event, f.data, (f.ts || Date.now() / 1000));
  if (!e || !f.session_id) return;
  noteActivity(key, f.event === "text_chunk" ? "typing" : f.event === "tool_use_start" ? "tool" : "", String(e.name || ""));
  if (!s.streams[key]?.viaEvents) append(key, e);
}

/** Start once: the first GET, the feed handlers, the poll while the feed is down. */
export function startFleet(): void {
  if (fleet.get().started) return;
  fleet.update(() => ({ started: true }));
  onEvent("agent_state", onAgentState);
  onEvent("agent_event", onAgentEvent);
  onEvent("fleet", onSessions);
  onEvent("sessions", () => later("load", 400, () => void load()));
  for (const k of RAW) onEvent(k, onRaw);
  for (const k of FIGURE_KINDS) onEvent(k, onFigures);
  for (const k of RELOAD) onEvent(k, () => later("load", 600, () => void load()));
  onEvent("dropped", () => later("load", 200, () => void load())); // 3.2.1.0: frames fell off the queue: re-read
  onFeedState((s) => { if (s === "open") later("load", 300, () => void load()); }); // a (re)opened stream missed its gap
  window.setInterval(() => {
    if (document.hidden) return;
    const st = fleet.get();
    const open = studio.get().feed.status === "open";
    const running = st.harnesses.some((h) => h.sessions.some((ss) => (ss.agents || []).some((a) => a.state === "running")));
    // 3.2.3.0 / 3.3.0.0 R7: a frame-based `running` the feed never corrects (an end frame lost, or a late frame after
    // it) is re-read while anything runs, every FLOOR_MS even while other frames keep coming: the view's later ask
    // wins (fresh.ts; the Linux runner kept a stopped agent `running` for 60 s)
    const since = Date.now() - lastAsk;
    if (open ? running && since >= FLOOR_MS : since >= POLL_MS) void load();
  }, TICK_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) later("load", 100, () => void load()); });
  void load();
  startPanels();
  startCaps();
  startMissions();
}
