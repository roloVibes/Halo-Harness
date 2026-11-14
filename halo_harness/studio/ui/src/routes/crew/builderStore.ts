// The builder box's store (3.6.0.0 R1; docs/STUDIO-builder.md): one conversation per tab, kept in this browser
// (localStorage, the last 40 lines; it never opens by itself: `open` starts false on every load), the preview of the
// last reply (its lines, each with a tick: a widening line comes unticked from the server and stays so until the
// person ticks it), Apply (POST builder/apply with the ticked ids only), Discard, and the receipt line with Undo
// (POST builder/undo). `fill` lines put drafted text into the form instead of writing a file.
import { api, ApiError } from "../../lib/api";
import { createStore, useStore } from "../../lib/store";
import { afterApply, crew, dirty, setForm } from "./store";
import type { Change, Meta, Msg } from "./types";

export type BuilderState = {
  cid: string;
  msgs: Msg[];
  open: boolean;
  text: string;
  sending: boolean;
  pending: Change[];
  meta: Meta | null;
  receipt: { line: string; undo: string; touched: string[] } | null;
  error: string;
};

const KEY = "halo.studio.builder.agents";
const newCid = () => `agents-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

function kept(): { cid: string; msgs: Msg[] } {
  try {
    const got = JSON.parse(localStorage.getItem(KEY) || "null");
    if (got && typeof got.cid === "string" && Array.isArray(got.msgs)) return { cid: got.cid, msgs: got.msgs };
  } catch {
    /* a private window keeps nothing */
  }
  return { cid: newCid(), msgs: [] };
}

function keep(cid: string, msgs: Msg[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ cid, msgs: msgs.slice(-40) }));
  } catch {
    /* nothing kept */
  }
}

export const builder = createStore<BuilderState>({ ...kept(), open: false, text: "", sending: false, pending: [], meta: null, receipt: null, error: "" });
export const useBuilder = <T,>(pick: (s: BuilderState) => T): T => useStore(builder, pick);
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

function say(m: Msg): void {
  builder.update((s) => {
    const msgs = [...s.msgs, m];
    keep(s.cid, msgs);
    return { msgs };
  });
}

export async function loadMeta(): Promise<void> {
  try {
    const meta = await api.get<Meta>("builder");
    builder.update(() => ({ meta }));
  } catch {
    /* the line beside the box says nothing new */
  }
}

export const setText = (text: string) => builder.update(() => ({ text }));
export const toggleOpen = () => builder.update((s) => ({ open: !s.open }));

/** "Write it for me": the box, filled, focused; the person sends it. */
export function prefill(text: string): void {
  builder.update(() => ({ text }));
  window.setTimeout(() => (document.querySelector("[data-testid=builder-input]") as HTMLInputElement | null)?.focus(), 0);
}

export async function send(textIn?: string): Promise<void> {
  const s = builder.get();
  const text = (textIn ?? s.text).trim();
  if (!text || s.sending) return;
  const c = crew.get();
  const selection = c.form ? { agent: c.form.name, ...(dirty(c) || !c.saved ? { unsaved: c.form } : {}) } : {};
  const history = s.msgs.slice(-8).map((m) => ({ me: !!m.me, text: m.text }));
  say({ me: true, text });
  builder.update(() => ({ text: textIn === undefined ? "" : s.text, sending: true, open: true, pending: [], error: "" }));
  try {
    const r = await api.post<{ reply: string; question?: Msg["question"]; changes: Change[]; cost_usd: number; meta: Meta }>(
      "builder/ask", { tab: "agents", selection, text, conversation_id: s.cid, history });
    say({ text: r.reply, question: r.question, cost: r.cost_usd });
    builder.update(() => ({ sending: false, pending: r.changes || [], meta: r.meta || builder.get().meta }));
  } catch (e) {
    const data = e instanceof ApiError ? (e.data as { meta?: Meta } | undefined) : undefined;
    say({ text: msg(e) });
    builder.update(() => ({ sending: false, ...(data?.meta ? { meta: data.meta } : {}) }));
  }
}

export function tick(id: string, on: boolean): void {
  builder.update((s) => ({ pending: s.pending.map((c) => (c.id === id ? { ...c, ticked: on } : c)) }));
}

export function discardPreview(): void {
  builder.update(() => ({ pending: [] }));
  say({ text: "Discarded: nothing changed." });
}

export async function apply(): Promise<void> {
  const s = builder.get();
  const ids = s.pending.filter((c) => c.ticked).map((c) => c.id);
  if (!ids.length) return discardPreview();
  try {
    const r = await api.post<{ undo_id: string; wrote: string[]; removed: string[]; skipped: string[]; filled: { field: string; value: string }[] }>(
      "builder/apply", { conversation_id: s.cid, change_ids: ids });
    for (const f of r.filled || []) setForm({ [f.field]: f.value });
    const touched = s.pending.filter((c) => ids.includes(c.id)).map((c) => c.target.split(":")[1]);
    const n = r.wrote.length + r.removed.length;
    const line = n ? `The builder wrote ${n} file${n > 1 ? "s" : ""}.` : r.filled?.length ? "Put into the form: read it, then Save." : "Nothing to write.";
    say({ text: line + (r.skipped?.length ? ` ${r.skipped.join(" ")}` : "") });
    builder.update(() => ({ pending: [], receipt: n ? { line, undo: r.undo_id, touched } : null }));
    await afterApply(touched);
  } catch (e) {
    say({ text: msg(e) });
  }
}

export async function undo(): Promise<void> {
  const r = builder.get().receipt;
  if (!r) return;
  try {
    const got = await api.post<{ restored: string[] }>("builder/undo", { undo_id: r.undo });
    builder.update(() => ({ receipt: null }));
    say({ text: `Undone: ${got.restored.length} file${got.restored.length === 1 ? "" : "s"} as before.` });
    await afterApply(r.touched);
  } catch (e) {
    say({ text: msg(e) });
  }
}

export function newConversation(): void {
  const cid = newCid();
  keep(cid, []);
  builder.update(() => ({ cid, msgs: [], pending: [], receipt: null }));
}
