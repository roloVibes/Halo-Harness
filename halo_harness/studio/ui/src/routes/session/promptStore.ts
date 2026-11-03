// The Prompt panel's state (3.3.11.0 R1, the owner: "a box to just type into like it is the tui but it's in
// session view"): the turns typed into this harness's sessions as the feed reports them (`user_message` frames
// of a main agent, with `via` and `receipt` when Studio sent them), the slash outputs shown here, the receipts'
// ladder (GET sessions/<sid>/receipts, re-read after a send, a turn's start and its end), the slash list (GET
// sessions/<sid>/slash: the TUI's own table and the session's custom commands), the asks' options, the
// draft, the image chip and the busy choice (promptSend.ts sends). History is per session, kept in this
// browser (localStorage, try/catch: a private window simply has none). `openPrompt` (Alt+Enter, the palette,
// `?prompt=1`, a `focus` frame with `prompt`) brings Session and the panel up and puts the keyboard in the box.
import { api } from "../../lib/api";
import { onEvent, type FeedFrame } from "../../lib/events";
import { createStore, goSection, studio, useStore } from "../../lib/store";
import { layoutStore, showPanel } from "../../lib/workspace/persist";
import type { PanelSpec } from "../../lib/workspace/types";
import { startLive } from "../shared/liveFeed";
import type { SteerImage } from "./steerImage";
import { enterSession } from "./store";

export type Receipt = { id: string; client_id: string; kind: string; state: string; reason?: string; turn?: number; at: number; sent_at?: number };
export type Turn = { n: number; sid: string; ts: number; text: string; via: string; receipt: string; turn: number };
export type Out = { n: number; sid: string; ts: number; line: string; lines: string[]; error?: boolean };
export type SlashRow = { name: string; group: string; help: string; args: string; source: string };
export type AskInfo = { kind: string; options: string[] };
export type Busy = { sid: string; text: string; line: string };
type State = {
  turns: Turn[]; outs: Out[]; receipts: Record<string, Receipt>; slash: Record<string, SlashRow[]>; asks: Record<string, AskInfo>;
  answered: Record<string, string>; busy: Busy | null; sending: boolean; draft: string; img: SteerImage | null; imgError: string; focus: number;
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
const MAX_HISTORY = 100;
let seq = 0;
let started = false;

export const prompt = createStore<State>({
  turns: [], outs: [], receipts: {}, slash: {}, asks: {}, answered: {}, busy: null, sending: false, draft: "", img: null, imgError: "", focus: 0,
});
export const usePrompt = <S,>(pick: (s: State) => S): S => useStore(prompt, pick);
export const nextN = (): number => ++seq;

const mainFrame = (f: FeedFrame) => !!f.session_id && (!f.agent_id || f.agent_id === "main");

function onUser(f: FeedFrame): void {
  if (!mainFrame(f)) return;
  const d = (f.data || {}) as Record<string, unknown>;
  const turn: Turn = { n: nextN(), sid: String(f.session_id), ts: Number(f.ts) || Date.now() / 1000, text: String(d.text || ""),
                       via: String(d.via || ""), receipt: String(d.receipt || ""), turn: Number(f.turn) || 0 };
  prompt.update((s) => ({ turns: [...s.turns, turn].slice(-MAX_TURNS) }));
  soon(turn.sid);
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

// -- history: per session, in this browser -------------------------------------------------------
const histKey = (sid: string) => `halo.studio.prompt.history.${sid}`;

export function history(sid: string): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(histKey(sid)) || "[]");
    return Array.isArray(v) ? v.map(String) : [];
  } catch {
    return [];
  }
}

export function pushHistory(sid: string, text: string): void {
  if (!sid || !text.trim()) return;
  try {
    const h = history(sid).filter((x) => x !== text);
    localStorage.setItem(histKey(sid), JSON.stringify([...h, text].slice(-MAX_HISTORY)));
  } catch {
    /* a private window keeps no history */
  }
}

export function setDraft(draft: string): void {
  prompt.update(() => ({ draft }));
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
  onEvent("turn_done", (f) => mainFrame(f) && soon(String(f.session_id)));
}
