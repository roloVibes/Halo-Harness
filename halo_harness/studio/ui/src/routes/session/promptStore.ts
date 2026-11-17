// The Prompt panel's state (3.3.11.0 R1, the owner: "a box to just type into like it is the tui but it's in
// session view"): the turns typed into this harness's sessions as the feed reports them (`user_message` frames
// of a main agent, with `via` and `receipt` when Studio sent them), the slash outputs shown here, the receipts'
// ladder (GET sessions/<sid>/receipts, re-read after a send, a turn's start and its end), the slash list (GET
// sessions/<sid>/slash: the TUI's own table and the session's custom commands), the asks' options, the
// draft, the image chip and the busy choice (promptSend.ts sends). History (promptDraft.ts) is per session, kept in this
// browser (localStorage, try/catch: a private window simply has none). `openPrompt` (Alt+Enter, the palette,
// `?prompt=1`, a `focus` frame with `prompt`) brings Session and the panel up and puts the keyboard in the box.
import { api } from "../../lib/api";
import { onEvent, type FeedFrame } from "../../lib/events";
import { createStore, goSection, studio, useStore } from "../../lib/store";
import { layoutStore, showPanel } from "../../lib/workspace/persist";
import type { PanelSpec } from "../../lib/workspace/types";
import { startLive } from "../shared/liveFeed";
import { answeredLine, INTERRUPTED } from "./promptWords";
import type { SteerImage } from "./steerImage";
import { enterSession } from "./store";

export type Receipt = { id: string; client_id: string; kind: string; state: string; reason?: string; turn?: number; at: number; sent_at?: number };
// 3.6.0.2 P22: `steer` marks a steer's row (the muted steering line under it)
export type Turn = { n: number; sid: string; ts: number; text: string; via: string; receipt: string; turn: number; steer?: boolean };
// 3.6.0.2 P20: `note` is a muted line of its own (`Interrupted.`), with no command above it
export type Out = { n: number; sid: string; ts: number; line: string; lines: string[]; error?: boolean; note?: boolean };
export type SlashRow = { name: string; group: string; help: string; args: string; source: string };
export type AskInfo = { kind: string; options: string[] };
export type Busy = { sid: string; text: string; line: string };
export type Heard = { line: string; ts: number };
type State = {
  turns: Turn[]; outs: Out[]; receipts: Record<string, Receipt>; slash: Record<string, SlashRow[]>; asks: Record<string, AskInfo>;
  answered: Record<string, string>; heard: Record<string, Heard>; busy: Busy | null; sending: boolean; draft: string;
  img: SteerImage | null; imgError: string; focus: number;
};

export const LADDER = ["sent", "delivered", "read", "replied"];
export const STATE_WORDS: Record<string, string> = {
  sent: "sent: Studio stored it",
  delivered: "delivered: the session took it",
  read: "read: it is in the model's input",
  replied: "replied: the turn that read it ended",
  failed: "failed",
};
const MAX_TURNS = 300;
let seq = 0;
let started = false;

export const prompt = createStore<State>({
  turns: [], outs: [], receipts: {}, slash: {}, asks: {}, answered: {}, heard: {}, busy: null, sending: false, draft: "", img: null, imgError: "",
  focus: 0,
});
export const usePrompt = <S,>(pick: (s: State) => S): S => useStore(prompt, pick);
export const nextN = (): number => ++seq;

const mainFrame = (f: FeedFrame) => !!f.session_id && (!f.agent_id || f.agent_id === "main");

function onUser(f: FeedFrame): void {
  if (!mainFrame(f)) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const turn: Turn = { n: nextN(), sid: String(f.session_id), ts: Number(f.ts) || Date.now() / 1000, text: String(d.text || ""),
                       via: String(d.via || ""), receipt: String(d.receipt || ""), turn: Number(f.turn) || 0 };
  soon(turn.sid);
  if (steering(turn.sid).includes(turn.text)) return void (turn.receipt && steerReceipt(turn.sid, turn.text, turn.receipt)); // P22: the apply-time copy
  prompt.update((s) => ({ turns: [...s.turns, turn].slice(-MAX_TURNS) }));
}

// -- 3.6.0.2 P22: a steer is ONE row, drawn by whichever comes first: the session's `steer_queued` or Studio's own
// answer `steered: true` (Studio remembers the text of its steer in flight); a `steer_queued`, a `user_message` or
// that answer whose text matches a steer drawn and still awaiting its `steer_applied` draws nothing (the terminal's
// rule, tui/dispatch.py). A refused or failed steer draws nothing.
const pendingSteers = new Map<string, string[]>();
let flight: { sid: string; text: string; drawn: boolean } | null = null;
const steering = (sid: string): string[] => pendingSteers.get(sid) || [];

function drawSteer(sid: string, text: string, ts: number, via: string, receipt = ""): void {
  pendingSteers.set(sid, [...steering(sid), text]);
  const turn: Turn = { n: nextN(), sid, ts, text, via, receipt, turn: 0, steer: true };
  prompt.update((s) => ({ turns: [...s.turns, turn].slice(-MAX_TURNS) }));
}

function steerReceipt(sid: string, text: string, receipt: string): void {
  prompt.update((s) => {
    const i = s.turns.map((t) => t.sid === sid && t.steer && t.text === text && !t.receipt).lastIndexOf(true);
    return i < 0 ? {} : { turns: s.turns.map((t, j) => (j === i ? { ...t, receipt } : t)) };
  });
}

function onSteerQueued(f: FeedFrame): void {
  if (!mainFrame(f)) return;
  const sid = String(f.session_id), text = String((f.data || {}).text || "");
  if (!text || steering(sid).includes(text)) return;
  const mine = !!flight && flight.sid === sid && flight.text === text;
  if (mine && flight!.drawn) return;
  if (mine) flight!.drawn = true;
  drawSteer(sid, text, Number(f.ts) || Date.now() / 1000, mine ? "studio" : "");
}

function onSteerApplied(f: FeedFrame): void {
  if (!mainFrame(f)) return;
  const sid = String(f.session_id), text = String((f.data || {}).text || ""), left = [...steering(sid)];
  const i = left.indexOf(text);
  if (i >= 0) left.splice(i, 1), pendingSteers.set(sid, left);
}

/** promptSend.ts: a steer is on its way (`text` as sent). */
export const steerSent = (sid: string, text: string): void => void (flight = { sid, text, drawn: false });

/** promptSend.ts: the answer to that steer; `steered` when the session took it as a steer. */
export function steerAnswered(steered: boolean, receipt = ""): void {
  const f = flight;
  flight = null;
  if (!f || !steered) return;
  if (f.drawn || steering(f.sid).includes(f.text)) return void (receipt && steerReceipt(f.sid, f.text, receipt));
  drawSteer(f.sid, f.text, Date.now() / 1000, "studio", receipt);
}

// -- 3.6.0.2 P23: an ask answered anywhere closes Studio's card with one line; P20: an interrupted turn says so.
function onAskAnswered(f: FeedFrame): void {
  if (!mainFrame(f)) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const id = String(d.request_id || "");
  if (id) prompt.update((s) => ({ heard: { ...s.heard, [id]: { line: answeredLine(String(d.where || ""), String(d.label ?? "")), ts: Number(f.ts) || Date.now() / 1000 } } }));
}

function onTurnDone(f: FeedFrame): void {
  if (!mainFrame(f)) return;
  const sid = String(f.session_id);
  soon(sid);
  if (String((f.data || {}).reason || "") !== "interrupted") return;
  const out: Out = { n: nextN(), sid, ts: Number(f.ts) || Date.now() / 1000, line: "", lines: [INTERRUPTED], note: true };
  prompt.update((s) => ({ outs: [...s.outs, out].slice(-MAX_TURNS) }));
}

function onAskFrame(f: FeedFrame): void {
  if (!mainFrame(f)) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const input = (d.input && typeof d.input === "object" ? d.input : {}) as { questions?: { options?: { label?: string }[] }[] };
  const options = (input.questions?.[0]?.options || []).map((o) => String(o?.label || "")).filter(Boolean).slice(0, 6);
  const kind = { permission_request: "permission", question: "question", plan_review: "plan", approval_request: "approval" }[f.event] || f.event;
  if (d.id) prompt.update((s) => ({ asks: { ...s.asks, [String(d.id)]: { kind, options } } }));
}

const timers = new Map<string, number>();
/** Read the receipts again shortly (a burst of frames reads once). */
export function soon(sid: string, ms = 250): void {
  window.clearTimeout(timers.get(sid));
  timers.set(sid, window.setTimeout(() => void loadReceipts(sid), ms));
}

export async function loadReceipts(sid: string): Promise<void> {
  if (!sid) return;
  try {
    const r = await api.get<{ receipts: Receipt[] }>(`sessions/${encodeURIComponent(sid)}/receipts`);
    const map: Record<string, Receipt> = {};
    for (const x of r.receipts || []) map[x.id] = x;
    prompt.update((s) => ({ receipts: { ...s.receipts, ...map } }));
  } catch {
    /* the marks keep what they showed; the next read catches up */
  }
}

export function noteReceipt(r: Receipt | null | undefined): void {
  if (r?.id) prompt.update((s) => ({ receipts: { ...s.receipts, [r.id]: r } }));
}

export async function loadSlash(sid: string): Promise<void> {
  if (!sid || prompt.get().slash[sid]) return;
  try {
    const rows = await api.get<SlashRow[]>(`sessions/${encodeURIComponent(sid)}/slash`);
    prompt.update((s) => ({ slash: { ...s.slash, [sid]: Array.isArray(rows) ? rows : [] } }));
  } catch {
    /* no list: the box still sends a typed command */
  }
}

/** The slash rows a draft asks for: "/" then a name being typed (no space yet), at most `max`. */
export function slashMatches(rows: SlashRow[] | undefined, draft: string, max = 8): SlashRow[] {
  const m = /^\/([^\s]*)$/.exec(draft);
  if (!m || !rows) return [];
  const want = m[1].toLowerCase();
  const starts = rows.filter((r) => r.name.toLowerCase().startsWith(want));
  const inside = want ? rows.filter((r) => !r.name.toLowerCase().startsWith(want) && r.name.toLowerCase().includes(want)) : [];
  return [...starts, ...inside].slice(0, max);
}

export function addOut(sid: string, line: string, lines: string[], error = false): void {
  const out: Out = { n: nextN(), sid, ts: Date.now() / 1000, line, lines, ...(error ? { error } : {}) };
  prompt.update((s) => ({ outs: [...s.outs, out].slice(-MAX_TURNS) }));
}

// -- opening it -------------------------------------------------------------------------------------
let spec: PanelSpec | null = null;

/** Session.tsx names its Prompt panel here (no import back the other way). */
export function registerPromptPanel(p: PanelSpec | undefined): void {
  spec = p || null;
}

function whenLaidOut(fn: () => void, tries = 60): void {
  if (layoutStore("session").get().layout || tries <= 0) fn();
  else window.setTimeout(() => whenLaidOut(fn, tries - 1), 50);
}

/** Session, the Prompt panel open, the keyboard in its box. */
export function openPrompt(): void {
  startPrompt();
  enterSession();
  if (studio.get().section !== "session") goSection("session");
  whenLaidOut(() => {
    if (spec) showPanel("session", spec);
    prompt.update((s) => ({ focus: s.focus + 1 }));
  });
}

/** `?prompt=1` on the Session route (`halo studio --session <id> --prompt`). */
export const promptAsked = (): boolean => /[?&]prompt=1(&|$)/.test(location.search);

/** The palette's entry (shell/commands.ts). */
export const promptCommand = () => ({ id: "session-prompt-open", group: "Session", label: "Prompt: type into this session", kbd: "Alt+Enter",
  hint: "the Prompt panel open, the keyboard in its box: a turn, or / for a command", run: openPrompt });

/** Start once: the frames the panel reads. */
export function startPrompt(): void {
  if (started) return;
  started = true;
  startLive(); // the replies, the tool lines and the asks the feed shows (Live's own store)
  onEvent("user_message", onUser);
  for (const k of ["permission_request", "question", "plan_review", "approval_request"]) onEvent(k, onAskFrame);
  onEvent("turn_done", onTurnDone);
  onEvent("steer_queued", onSteerQueued); // 3.6.0.2 P22
  onEvent("steer_applied", onSteerApplied);
  onEvent("ask_answered", onAskAnswered); // 3.6.0.2 P23
}
