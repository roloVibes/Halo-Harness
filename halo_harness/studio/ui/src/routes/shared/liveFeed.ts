// The Session's Live column (3.1.5.0 R3): ONE list of everything the agents
// do, in the order it arrives, from the same feed frames the per-agent
// streams read (routes/fleet/streams.ts, sync.ts): text chunks, tool starts
// and results, a followed agent's `agent_event` entries (its raw frames are
// skipped then, as the streams skip them), and the four asks. liveTree.ts
// adds what the agent tree says (a spawn, done with its last text, failed,
// a steer echoed) and each agent's backlog (its tail, inserted by time).
// An agent's text joins its own line while that line is recent (the column
// reads as one paragraph per agent, not a chunk per frame); a tool row takes
// its result when it lands (3.1.7.0 R1: its first line, and the whole of it
// for the click that opens the row). At most MAX_LINES are kept. `open` is the tool
// each agent runs right now and since when: the map's "Bash 12s" reads it. 3.2.0.0 R3: a pack's
// `pack_event` is one line (kind "pack") with the pack's label and its line template (routes/packs/events.ts).
// 3.2.2.0 R4: a session's `turn_marker` (`◼ done · 42 s · 3 tools`, `◼ waiting on you: ...`, `◼ stopped: ...`) is a state line.
// 3.3.0.0 R6: a steer you send (`addSteer`) lands right under its target row (the anchor session/steer.ts names), and
// the agent's next row of its own (text, a tool call, an output) is marked `after` ("after your steer").
import { onEvent, type FeedFrame } from "../../lib/events";
import { createStore, useStore } from "../../lib/store";
import { fleet, findAgent, keyOf, localId } from "../fleet/store";
import type { AgentKey, Entry } from "../fleet/types";
import { lineOf, packOf } from "../packs/events";
import { ASK_EVENTS, askOfFrame, askOfRow, withAsk, type AskLine, type RowAsk } from "./liveAsk";
import type { LiveKind, LiveLine } from "./liveTypes";
import { picOf } from "../session/browserPic";

export type { LiveKind, LiveLine, Talk } from "./liveTypes";
export type OpenTool = { tool: string; id: string; t0: number };
export type LiveState = { lines: LiveLine[]; open: Record<AgentKey, OpenTool>; started: boolean };

export const MAX_LINES = 1500;
const TEXT_MAX = 1600;
const FULL_MAX = 4000;
const JOIN_LINES = 8;
const JOIN_MS = 6000;
let seq = 0;
const ANSWERS: LiveKind[] = ["text", "thinking", "tool", "output", "error"];
const steered = new Set<AgentKey>();
/** 3.3.16.2: agents whose thoughts come as `thinking_chunk` frames (liveThink.ts): their followed `thinking` entries are not drawn twice. */
export const thinkSeen = new Set<AgentKey>();
/** 3.3.16.2: the agent's hand-back already landed as a TALK row (liveTalk.ts): its OUT would say it twice. */
export const talkedBack = (key: AgentKey) => live.get().lines.slice(-60).some((l) => l.key === key && l.kind === "talk" && l.talk?.why === "hand-back");
let anchorOf: (key: AgentKey) => number = () => 0;

/** session/steer.ts: the row a steer to `key` lands under (0: at the end). */
export function setSteerAnchor(fn: (key: AgentKey) => number): void {
  anchorOf = fn;
}

export const live = createStore<LiveState>({ lines: [], open: {}, started: false });

export function useLive<S>(select: (s: LiveState) => S): S {
  return useStore(live, select);
}

const keepEnd = (t: string) => (t.length > TEXT_MAX ? "..." + t.slice(-(TEXT_MAX - 3)) : t);
export const firstLine = (t: string | undefined) => String(t || "").split(/\r?\n/).map((x) => x.trim()).find(Boolean)?.slice(0, 160) || "";
const fullOf = (t: string | undefined) => (String(t || "").length > FULL_MAX ? String(t).slice(0, FULL_MAX) + "\n..." : String(t || "")).replace(/\s+$/, "");

type NewLine = Omit<LiveLine, "n" | "t0"> & { t0?: number };

/** Add one line; `at` keeps the list in time order (a backlog entry), else it goes last. */
export function addLine(l: NewLine, at = false): void {
  const after = !at && ANSWERS.includes(l.kind) && steered.delete(l.key);
  live.update((s) => {
    const line: LiveLine = { t0: at ? l.ts * 1000 : Date.now(), ...l, n: ++seq, ...(after ? { after } : {}) };
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
    if (x.kind === kind && now - (x.ended || x.t0) < JOIN_MS && !steered.has(key)) {
      const lines = s.lines.slice();
      lines[j] = { ...x, text: keepEnd(x.text + text), ended: now };
      live.update(() => ({ lines }));
      return;
    }
    break;
  }
  addLine({ key, kind, ts, text: keepEnd(text), ended: now });
}

/** A steer you sent to `key` (`to`: its name): one row under the target row, after any steer already there. */
export function addSteer(key: AgentKey, text: string, ts: number, to: string): void {
  const anchor = anchorOf(key);
  live.update((s) => {
    const line: LiveLine = { key, kind: "you", ts, t0: Date.now(), text: keepEnd(text), to, n: ++seq };
    let i = anchor ? s.lines.findIndex((x) => x.n === anchor) : -1;
    if (i < 0) return { lines: [...s.lines, line].slice(-MAX_LINES) };
    for (i++; i < s.lines.length && s.lines[i].kind === "you" && s.lines[i].key === key; i++);
    return { lines: [...s.lines.slice(0, i), line, ...s.lines.slice(i)].slice(-MAX_LINES) };
  });
  steered.add(key);
}

export function toolStart(key: AgentKey, id: string, tool: string, ts: number, target = ""): void {
  const cur = String(findAgent(fleet.get(), key)?.a.current || "");
  addLine({ key, kind: "tool", ts, text: "", tool, id, target: target || (cur.startsWith(tool + ":") ? cur.slice(tool.length + 1).trim() : "") });
}

/** The newest open tool row of `key` (with `id` when the frame names one) takes its result (and its policy line). */
export function toolEnd(key: AgentKey, id: string, text: string, isError: boolean, policy = "", picture = ""): void {
  live.update((s) => {
    const open = { ...s.open };
    if (open[key] && (!id || !open[key].id || open[key].id === id)) delete open[key];
    for (let j = s.lines.length - 1; j >= Math.max(0, s.lines.length - 400); j--) {
      const x = s.lines[j];
      if (x.key === key && x.kind === "tool" && !x.ended && (!id || !x.id || x.id === id)) {
        const lines = s.lines.slice();
        const pic = picOf(lines, j, x, picture || text);
        lines[j] = { ...x, result: firstLine(text) || (isError ? "failed" : "ok"), full: fullOf(text), ended: Date.now(), error: isError, ...(policy ? { policy } : {}), ...(pic ? { pic } : {}) };
        return { lines, open };
      }
    }
    return { open };
  });
}

/** An ask's line in (liveAsk.ts withAsk: a handed one once, its frame fills it). */
const putAsk = (key: AgentKey, a: AskLine) => live.update((s) => ({ lines: withAsk(s.lines, key, a, () => ({ t0: Date.now(), n: ++seq })).slice(-MAX_LINES) }));

/** 3.6.0.2 P9: the door of an ask from an agent on no box (glance/openAsk.ts) hands its row to the Feed: shown at once. */
export const handAsk = (key: AgentKey, row: RowAsk) => putAsk(key, askOfRow(row));

/** One transcript entry (a followed agent's `agent_event`, or its backlog with `at`) as a line. */
export function fromEntry(key: AgentKey, e: Entry, at = false): void {
  const ts = Number(e.ts) || Date.now() / 1000;
  const name = String(e.name || "?");
  const label = String(e.label || "");
  const target = label.startsWith(name + ":") ? label.slice(name.length + 1).trim() : "";
  if (e.kind === "thinking" && !at && thinkSeen.has(key)) return;
  if ((e.kind === "text" || e.kind === "thinking") && !at) return addText(key, e.kind, String(e.text || ""), ts);
  if (e.kind === "text" || e.kind === "thinking") return addLine({ key, kind: e.kind, ts, text: keepEnd(String(e.text || "")) }, true);
  if (e.kind === "tool_call") return at ? addLine({ key, kind: "tool", ts, text: "", tool: name, id: String(e.id || ""), target, ended: ts * 1000 }, true) : toolStart(key, String(e.id || ""), name, ts, target);
  if (e.kind === "tool_result") return at ? backlogResult(key, e) : toolEnd(key, String(e.id || ""), String(e.text || ""), !!e.is_error, String(e.policy || ""), String(e.picture || ""));
  if (e.kind === "spawn") return addLine({ key, kind: "spawn", ts, text: label || `${name}: ${e.task || ""}` }, at);
  if (e.kind === "handback") return at || !talkedBack(key) ? addLine({ key, kind: "output", ts, text: keepEnd(String(e.text || "")) }, at) : undefined;
  if (e.kind === "user") return addLine({ key, kind: e.you ? "you" : "asked", ts, text: keepEnd(String(e.text || "")) }, at);
  if (e.kind === "error") return addLine({ key, kind: "error", ts, text: String(e.text || e.reason || "error").slice(0, 300), ...errTypeOf(e) }, at);
}

/** 3.6.0.17 P2: the error's own type the entry carries (agent_transcript.py `err_type`), kept on its line. */
const errTypeOf = (e: Entry): { errType?: string } => {
  const t = (e as { err_type?: unknown }).err_type;
  return t ? { errType: String(t) } : {};
};

/** A backlog result: the tool row it belongs to (by id) takes it. */
function backlogResult(key: AgentKey, e: Entry): void {
  live.update((s) => {
    const j = s.lines.findIndex((x) => x.key === key && x.kind === "tool" && !!e.id && x.id === String(e.id));
    if (j < 0) return {};
    const lines = s.lines.slice();
    const pic = picOf(lines, j, lines[j], String(e.picture || e.text || ""));
    lines[j] = { ...lines[j], result: firstLine(e.text) || (e.is_error ? "failed" : "ok"), full: fullOf(e.text), error: !!e.is_error, ...(e.policy ? { policy: e.policy } : {}), ...(pic ? { pic } : {}) };
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
  else if (f.event === "tool_result") toolEnd(key, String(d.id || ""), typeof d.content === "string" ? d.content : String(d.summary || ""), !!d.is_error, policyLine(d.policy));
}

/** 3.3.10.0 R2: a tool_result frame's `policy: {line, verdicts}` as its line ("" when none). */
const policyLine = (p: unknown) => (p && typeof p === "object" ? String((p as { line?: unknown }).line || "") : "");

function onAgentEvent(f: FeedFrame): void {
  const e = f.data as Entry | null;
  if (!e || typeof e.kind !== "string" || !f.session_id) return;
  fromEntry(frameKey(f), { ...e, ts: e.ts || f.ts });
}

function onAsk(f: FeedFrame): void {
  if (!f.session_id) return;
  putAsk(frameKey(f), askOfFrame(f.event, (f.data || {}) as Record<string, unknown>, Number(f.ts) || Date.now() / 1000));
}

/** Start once (Session's Live panel, the map's tool clock): the feed handlers (liveTree.ts adds the tree's). */
export function startLive(): void {
  if (live.get().started) return;
  live.update(() => ({ started: true }));
  for (const k of ["text_chunk", "tool_use_start", "tool_result"]) onEvent(k, onRaw);
  onEvent("agent_event", onAgentEvent);
  for (const k of ASK_EVENTS) onEvent(k, onAsk);
  onEvent("pack_event", onPack);
  onEvent("turn_marker", onMarker);
}

/** 3.2.2.0 R4: the line a turn ends with (done / waiting on you / stopped) and the loop's nudge and resend notes, as a state line. */
function onMarker(f: FeedFrame): void {
  if (!f.session_id) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const text = String(d.text || "").trim();
  if (!text) return;
  addLine({ key: frameKey(f), kind: "state", ts: Number(f.ts) || Date.now() / 1000, text, state: "marker-" + String(d.state || "done") });
}

/** A pack's frame: one line under the pack's name, in this harness's column. */
function onPack(f: FeedFrame): void {
  const d = packOf(f.data);
  if (!d) return;
  const l = lineOf(d.pack, d.kind, d.data);
  addLine({ key: keyOf(String(f.harness || localId() || ""), "", "pack:" + d.pack), kind: "pack", ts: Number(f.ts) || Date.now() / 1000, text: l.text, label: l.label });
}

/** The tool `key` runs now (null when none), from the feed. */
export function useOpenTool(key: AgentKey): OpenTool | null {
  return useLive((s) => s.open[key] || null);
}
