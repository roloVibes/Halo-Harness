// One stream per agent: its backlog (`agent_tail` when it is opened), then
// what the feed pushes: `agent_event` entries once it is followed
// (`agent_follow`), else the raw `text_chunk` / `tool_use_start` /
// `tool_result` frames turned into the same entries. A steer sent from here
// is echoed at once with `you`. The Thinking / Working / Output views
// (StreamViews.tsx) read the entries; the shell keeps at most MAX of them.
import { api, ApiError } from "../../lib/api";
import { fleet, findAgent, parseKey } from "./store";
import type { AgentKey, Entry, Stream } from "./types";

const MAX = 400;
const TAIL_N = 200;

export const EMPTY: Stream = { entries: [], loaded: false, loading: false, error: "", viaEvents: false, following: false, tick: 0 };

function patch(key: AgentKey, fn: (st: Stream) => Partial<Stream>): void {
  fleet.update((s) => {
    const cur = s.streams[key] || EMPTY;
    const next = { ...cur, ...fn(cur) };
    return { streams: { ...s.streams, [key]: { ...next, tick: cur.tick + 1 } } };
  });
}

export function append(key: AgentKey, e: Entry): void {
  patch(key, (st) => ({ entries: merge(st.entries, e).slice(-MAX) }));
}

/** Text chunks of the same kind join the entry before them (the stream reads as one text). */
function merge(list: Entry[], e: Entry): Entry[] {
  const last = list[list.length - 1];
  if (last && (e.kind === "text" || e.kind === "thinking") && last.kind === e.kind && !last.you)
    return [...list.slice(0, -1), { ...last, text: (last.text || "") + (e.text || "") }];
  return [...list, e];
}

/** A raw feed frame as a stream entry, or null for a kind the stream does not show. */
export function rawEntry(kind: string, data: Record<string, unknown> | null, ts: number): Entry | null {
  const d = data || {};
  if (kind === "text_chunk") return { kind: "text", text: String(d.text || ""), ts };
  if (kind === "tool_use_start") return { kind: "tool_call", id: String(d.id || ""), name: String(d.name || "?"), label: String(d.name || "?"), ts };
  if (kind === "tool_result") {
    const text = typeof d.content === "string" ? d.content : String(d.summary || "");
    return { kind: "tool_result", id: String(d.id || ""), name: d.name ? String(d.name) : null, text: text.slice(0, 2000), is_error: !!d.is_error, ts };
  }
  return null;
}

function tailPath(key: AgentKey): { local: boolean; path: string; sid: string; aid: string; hid: string } {
  const { h, s, a } = parseKey(key);
  const ref = findAgent(fleet.get(), key);
  const local = !!ref?.h.local;
  const path = local ? `sessions/${encodeURIComponent(s)}/agents/${encodeURIComponent(a)}` : `fleet/${encodeURIComponent(h)}/${encodeURIComponent(s)}/agents/${encodeURIComponent(a)}`;
  return { local, path, sid: s, aid: a, hid: h };
}

/** The agent's backlog: its last TAIL_N entries, with anything that came in meanwhile kept after them. */
export async function loadTail(key: AgentKey): Promise<void> {
  const st = fleet.get().streams[key];
  if (st?.loading) return;
  patch(key, () => ({ loading: true, error: "" }));
  const { local, path } = tailPath(key);
  try {
    let events: Entry[] = [];
    if (local) events = (await api.get<{ events: Entry[] }>(`${path}/tail`, { n: TAIL_N })).events || [];
    else {
      const r = await api.post<{ result?: { events?: Entry[] } }>(`${path}/command`, { cmd: "tail", n: TAIL_N });
      events = r.result?.events || [];
    }
    const lastTs = events.reduce((m, e) => Math.max(m, Number(e.ts) || 0), 0);
    patch(key, (cur) => ({
      loading: false,
      loaded: true,
      entries: [...events, ...cur.entries.filter((e) => e.you || (Number(e.ts) || 0) > lastTs)].slice(-MAX),
    }));
  } catch (e) {
    patch(key, () => ({ loading: false, loaded: true, error: e instanceof ApiError ? e.message : String(e) }));
  }
}

/** agent_follow on or off: a followed agent's entries are pushed as `agent_event` frames. */
export async function follow(key: AgentKey, on: boolean): Promise<void> {
  const { path } = tailPath(key);
  try {
    await api.post(`${path}/command`, { cmd: "follow", on });
    patch(key, () => ({ following: on }));
  } catch {
    patch(key, () => ({ following: false }));
  }
}

let watched: AgentKey = "";

/** Open an agent's stream: the backlog once, follow it, and stop following the one before (unless pinned). */
export function watch(key: AgentKey): void {
  if (!key) return;
  const st = fleet.get().streams[key];
  if (!st?.loaded) void loadTail(key);
  if (!st?.following) void follow(key, true);
  const prev = watched;
  watched = key;
  if (prev && prev !== key && prev !== fleet.get().pinned) void follow(prev, false);
}

// -- what the views show -----------------------------------------------------------
const THINKING = new Set(["text", "thinking", "user", "note", "control", "ask", "error", "done"]);
const WORKING = new Set(["tool_call", "spawn"]);

/** Following an agent is how Studio reads it, not something it did: those control lines stay out. */
const QUIET_CONTROLS = new Set(["agent_follow", "agent_tail", "agents"]);

export function thinkingOf(entries: Entry[]): Entry[] {
  return entries.filter((e) => THINKING.has(e.kind) && !(e.kind === "control" && QUIET_CONTROLS.has(String(e.cmd))));
}

export type ToolRow = { call: Entry; result: Entry | null };

export function workingOf(entries: Entry[]): ToolRow[] {
  const results = new Map<string, Entry>();
  for (const e of entries) if (e.kind === "tool_result" && e.id) results.set(String(e.id), e);
  return entries.filter((e) => WORKING.has(e.kind)).map((call) => ({ call, result: call.id ? results.get(String(call.id)) || null : null }));
}

/** Its hand-back if it has one, else the text it wrote after its last tool call. */
export function outputOf(entries: Entry[]): string {
  const hand = [...entries].reverse().find((e) => e.kind === "handback");
  if (hand) return hand.text || "";
  const out: string[] = [];
  for (let i = entries.length - 1; i >= 0; i--) {
    const e = entries[i];
    if (e.kind === "text") out.unshift(e.text || "");
    else if (e.kind === "tool_call" || e.kind === "spawn" || e.kind === "user") break;
  }
  return out.join("");
}
