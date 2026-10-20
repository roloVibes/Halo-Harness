// The Session's Live column (3.1.5.0 R3): ONE list of everything the agents
// do, in the order it arrives, from the same feed frames the per-agent
// streams read (routes/fleet/streams.ts, sync.ts): text chunks, tool starts
// and results, a followed agent's `agent_event` entries (its raw frames are
// skipped then, as the streams skip them), and the four asks. liveTree.ts
// adds what the agent tree says (a spawn, done with its last text, failed,
// a steer echoed) and each agent's backlog (its tail, inserted by time).
// An agent's text joins its own line while that line is recent (the column
// reads as one paragraph per agent, not a chunk per frame); a tool row takes
// its result when it lands. At most MAX_LINES are kept. `open` is the tool
// each agent runs right now and since when: the map's "Bash 12s" reads it.
import { onEvent, type FeedFrame } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { fleet, findAgent, keyOf, localId } from "../fleet/store";
import type { AgentKey, Entry } from "../fleet/types";

export type LiveKind = "text" | "thinking" | "tool" | "output" | "ask" | "spawn" | "state" | "you" | "asked" | "error";
export type LiveLine = {
  n: number;
  key: AgentKey;
  kind: LiveKind;
  /** When it happened (unix seconds, the frame's own time). */
  ts: number;
  /** When it arrived here (ms): a running tool's clock. */
  t0: number;
  text: string;
  tool?: string;
  target?: string;
  id?: string;
  result?: string;
  /** When its result landed (ms). */
  ended?: number;
  error?: boolean;
  ask?: string;
  state?: string;
};
export type OpenTool = { tool: string; id: string; t0: number };
export type LiveState = { lines: LiveLine[]; open: Record<AgentKey, OpenTool>; started: boolean };

export const MAX_LINES = 1500;
const TEXT_MAX = 1600;
const JOIN_LINES = 8;
const JOIN_MS = 6000;
let seq = 0;

export const live = createStore<LiveState>({ lines: [], open: {}, started: false });

export function useLive<S>(select: (s: LiveState) => S): S {
  return useStore(live, select);
}

const clip = (t: string) => (t.length > TEXT_MAX ? "..." + t.slice(-(TEXT_MAX - 3)) : t);
export const firstLine = (t: string | undefined) => String(t || "").split(/\r?\n/).map((x) => x.trim()).find(Boolean)?.slice(0, 160) || "";

type NewLine = Omit<LiveLine, "n" | "t0"> & { t0?: number };

/** Add one line; `at` keeps the list in time order (a backlog entry), else it goes last. */
export function addLine(l: NewLine, at = false): void {
  live.update((s) => {
    const line: LiveLine = { t0: at ? l.ts * 1000 : Date.now(), ...l, n: ++seq };
    const open = l.kind === "tool" && !l.ended && !at ? { ...s.open, [l.key]: { tool: l.tool || "?", id: l.id || "", t0: line.t0 } } : s.open;
    if (!at) return { lines: [...s.lines, line].slice(-MAX_LINES), open };
    let i = s.lines.length;
    while (i > 0 && s.lines[i - 1].ts > line.ts) i--;
    const lines = [...s.lines.slice(0, i), line, ...s.lines.slice(i)];
    return { lines: lines.slice(-MAX_LINES), open };
  });
}

/** Text joins the agent's own recent text line (no line of that agent after it), else starts one. */
export function addText(key: AgentKey, kind: "text" | "thinking", text: string, ts: number): void {
  if (!text) return;
  const s = live.get();
  const now = Date.now();
  for (let j = s.lines.length - 1; j >= Math.max(0, s.lines.length - JOIN_LINES); j--) {
    const x = s.lines[j];
    if (x.key !== key) continue;
    if (x.kind === kind && now - (x.ended || x.t0) < JOIN_MS) {
      const lines = s.lines.slice();
      lines[j] = { ...x, text: clip(x.text + text), ended: now };
      live.update(() => ({ lines }));
      return;
    }
    break;
  }
  addLine({ key, kind, ts, text: clip(text), ended: now });
}

export function toolStart(key: AgentKey, id: string, tool: string, ts: number, target = ""): void {
  const cur = String(findAgent(fleet.get(), key)?.a.current || "");
  addLine({ key, kind: "tool", ts, text: "", tool, id, target: target || (cur.startsWith(tool + ":") ? cur.slice(tool.length + 1).trim() : "") });
}

/** The newest open tool row of `key` (with `id` when the frame names one) takes its result. */
export function toolEnd(key: AgentKey, id: string, text: string, isError: boolean): void {
  live.update((s) => {
    const open = { ...s.open };
    if (open[key] && (!id || !open[key].id || open[key].id === id)) delete open[key];
    for (let j = s.lines.length - 1; j >= Math.max(0, s.lines.length - 400); j--) {
      const x = s.lines[j];
      if (x.key === key && x.kind === "tool" && !x.ended && (!id || !x.id || x.id === id)) {
        const lines = s.lines.slice();
        lines[j] = { ...x, result: firstLine(text) || (isError ? "failed" : "ok"), ended: Date.now(), error: isError };
        return { lines, open };
      }
    }
    return { open };
  });
}

const ASK_LABEL: Record<string, string> = { permission_request: "asks to run", question: "asks you", plan_review: "has a plan for you to review", approval_request: "asks for your approval" };
const ASK_KIND: Record<string, string> = { permission_request: "permission", question: "question", plan_review: "plan", approval_request: "approval" };

function askText(event: string, d: Record<string, unknown>): string {
  const input = (d.input && typeof d.input === "object" ? d.input : {}) as Record<string, unknown>;
  const what = String(input.question || d.question || d.text || input.command || d.name || "").replace(/\s+/g, " ").slice(0, 220);
  return `${ASK_LABEL[event] || "asks"}${what ? ": " + what : ""}`;
}

/** One transcript entry (a followed agent's `agent_event`, or its backlog with `at`) as a line. */
export function fromEntry(key: AgentKey, e: Entry, at = false): void {
  const ts = Number(e.ts) || Date.now() / 1000;
  const name = String(e.name || "?");
  const label = String(e.label || "");
  const target = label.startsWith(name + ":") ? label.slice(name.length + 1).trim() : "";
  if ((e.kind === "text" || e.kind === "thinking") && !at) return addText(key, e.kind, String(e.text || ""), ts);
  if (e.kind === "text" || e.kind === "thinking") return addLine({ key, kind: e.kind, ts, text: clip(String(e.text || "")) }, true);
  if (e.kind === "tool_call") return at ? addLine({ key, kind: "tool", ts, text: "", tool: name, id: String(e.id || ""), target, ended: ts * 1000 }, true) : toolStart(key, String(e.id || ""), name, ts, target);
  if (e.kind === "tool_result") return at ? backlogResult(key, e) : toolEnd(key, String(e.id || ""), String(e.text || ""), !!e.is_error);
  if (e.kind === "spawn") return addLine({ key, kind: "spawn", ts, text: label || `${name}: ${e.task || ""}` }, at);
  if (e.kind === "handback") return addLine({ key, kind: "output", ts, text: clip(String(e.text || "")) }, at);
  if (e.kind === "user") return addLine({ key, kind: e.you ? "you" : "asked", ts, text: clip(String(e.text || "")) }, at);
  if (e.kind === "error") return addLine({ key, kind: "error", ts, text: String(e.text || e.reason || "error").slice(0, 300) }, at);
}

/** A backlog result: the tool row it belongs to (by id) takes it. */
function backlogResult(key: AgentKey, e: Entry): void {
  live.update((s) => {
    const j = s.lines.findIndex((x) => x.key === key && x.kind === "tool" && !!e.id && x.id === String(e.id));
    if (j < 0) return {};
    const lines = s.lines.slice();
    lines[j] = { ...lines[j], result: firstLine(e.text) || (e.is_error ? "failed" : "ok"), error: !!e.is_error };
    return { lines };
  });
}

function frameKey(f: FeedFrame): AgentKey {
  return keyOf(String(f.harness || localId() || ""), String(f.session_id || ""), String(f.agent_id || "main"));
}

const viaEvents = (key: AgentKey) => !!fleet.get().streams[key]?.viaEvents;

function onRaw(f: FeedFrame): void {
  if (!f.session_id) return;
  const key = frameKey(f);
  if (viaEvents(key)) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const ts = Number(f.ts) || Date.now() / 1000;
  if (f.event === "text_chunk") addText(key, "text", String(d.text || ""), ts);
  else if (f.event === "tool_use_start") toolStart(key, String(d.id || ""), String(d.name || "?"), ts);
  else if (f.event === "tool_result") toolEnd(key, String(d.id || ""), typeof d.content === "string" ? d.content : String(d.summary || ""), !!d.is_error);
}

function onAgentEvent(f: FeedFrame): void {
  const e = f.data as Entry | null;
  if (!e || typeof e.kind !== "string" || !f.session_id) return;
  fromEntry(frameKey(f), { ...e, ts: e.ts || f.ts });
}

function onAsk(f: FeedFrame): void {
  if (!f.session_id) return;
  const d = (f.data || {}) as Record<string, unknown>;
  addLine({ key: frameKey(f), kind: "ask", ts: Number(f.ts) || Date.now() / 1000, text: askText(f.event, d), ask: ASK_KIND[f.event] || f.event, id: String(d.id || "") });
}

/** Start once (Session's Live panel, the map's tool clock): the feed handlers (liveTree.ts adds the tree's). */
export function startLive(): void {
  if (live.get().started) return;
  live.update(() => ({ started: true }));
  for (const k of ["text_chunk", "tool_use_start", "tool_result"]) onEvent(k, onRaw);
  onEvent("agent_event", onAgentEvent);
  for (const k of Object.keys(ASK_LABEL)) onEvent(k, onAsk);
}

/** The tool `key` runs now (null when none), from the feed. */
export function useOpenTool(key: AgentKey): OpenTool | null {
  return useLive((s) => s.open[key] || null);
}
