// 3.3.7.0 R5: the steward's chat slice (StewardChat.tsx; studio/local_steward_chat_api.py). The log is the steward's
// own session log (ollama/steward-chat.jsonl): GET local/steward/chat reads it, POST local/steward/chat asks one turn
// (the steward's own model; `bigger` sends the same context once to the session's main model, its cost read first
// from GET local/steward/bigger-cost). A tool's button (retire, add, bench, battery) posts to the route that does that
// one thing; nothing runs until it is pressed. The picker: GET local/steward/candidates, POST local/steward/model.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";

export type ChatButton = { id?: string; verb: string; label: string; route: string; body: Record<string, unknown>; cli: string };
export type ChatRow = { id: string; at: number; role: "user" | "steward" | "tool" | "button" | "bigger"; text: string;
  model?: string; cost?: string; tool?: string; ok?: boolean; action?: ChatButton };
export type Candidate = { model: string; ref: string; host: string; installed: boolean; gb: number | null;
  fits_beside_main: boolean | null; tool_calls: string; why: string; download_gb: number | null; minutes: number };
type Said = { ok: boolean; text: string };
type Chat = { rows: ChatRow[] | null; model: string | null; why: string; busy: boolean; error: string; bigger: string;
  cands: Candidate[] | null; chosen: string | null; said: Record<string, Said> };

export const chat = createStore<Chat>({ rows: null, model: null, why: "", busy: false, error: "", bigger: "", cands: null,
  chosen: null, said: {} });

export function useChat<T>(pick: (s: Chat) => T): T {
  return useStore(chat, pick);
}

function msg(e: unknown): string {
  return e instanceof ApiError ? e.message : String(e);
}

export async function loadChat(): Promise<void> {
  try {
    const r = await api.get<{ rows: ChatRow[]; model: string | null; why: string }>("local/steward/chat");
    chat.update(() => ({ rows: r.rows, model: r.model, why: r.why, error: "" }));
  } catch (e) {
    chat.update(() => ({ error: msg(e) }));
  }
}

export async function loadBiggerCost(question: string): Promise<void> {
  try {
    const r = await api.get<{ line: string }>("local/steward/bigger-cost", question ? { question } : undefined);
    chat.update(() => ({ bigger: r.line }));
  } catch (e) {
    chat.update(() => ({ bigger: msg(e) }));
  }
}

export async function ask(question: string, bigger = false): Promise<void> {
  const q = question.trim();
  if (!q) return;
  chat.update((s) => ({ busy: true, error: "", rows: [...(s.rows || []), { id: `q-${Date.now()}`, at: Date.now() / 1000, role: "user", text: q }] }));
  try {
    await api.post("local/steward/chat", { question: q, bigger });
  } catch (e) {
    chat.update(() => ({ error: msg(e) }));
  }
  chat.update(() => ({ busy: false }));
  await loadChat();
}

/** A button the chat left: the one route that does its one thing. */
export async function press(b: ChatButton, key: string): Promise<void> {
  try {
    const r = await api.post<{ say?: string; line?: string }>(b.route, b.body);
    chat.update((s) => ({ said: { ...s.said, [key]: { ok: true, text: r.say || r.line || `${b.label}: started` } } }));
  } catch (e) {
    chat.update((s) => ({ said: { ...s.said, [key]: { ok: false, text: msg(e) } } }));
  }
}

export async function loadCandidates(): Promise<void> {
  try {
    const r = await api.get<{ candidates: Candidate[]; chosen: string | null; why: string }>("local/steward/candidates");
    chat.update(() => ({ cands: r.candidates, chosen: r.chosen, why: r.why }));
  } catch (e) {
    chat.update(() => ({ error: msg(e) }));
  }
}

export async function pick(ref: string): Promise<void> {
  try {
    await api.post("local/steward/model", { model: ref });
  } catch (e) {
    chat.update(() => ({ error: msg(e) }));
  }
  await Promise.all([loadCandidates(), loadChat()]);
}
