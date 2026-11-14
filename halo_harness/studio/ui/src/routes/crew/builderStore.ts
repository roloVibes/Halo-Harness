// The builder box's store (3.6.0.0 R1; docs/STUDIO-builder.md): one conversation per tab, kept in this browser
// (localStorage, the last 40 lines; it never opens by itself: `open` starts false on every load), the preview of the
// last reply (its lines, each with a tick: a widening line comes unticked from the server and stays so until the
// person ticks it), Apply (POST builder/apply with the ticked ids only), Discard, and the receipt line with Undo
// (POST builder/undo). `fill` lines put drafted text into the form instead of writing a file.
// 3.6.0.0 R2: a store per tab (Agents, Workflows), each with its own conversation; a tab says what is open in it, what
// to do after an Apply or an Undo, and where a run the builder started (try_agent / try_workflow) is shown (`onTab`).
import { api, ApiError } from "../../lib/api";
import { createStore, useStore, type Store } from "../../lib/store";
import { afterApply, crew, dirty, setForm } from "./store";
import { showTry } from "./tryStore";
import type { Change, Meta, Msg, TryRec } from "./types";

export type Tab = "agents" | "workflows";

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

type Hooks = { selection: () => object; after: (targets: string[]) => Promise<void>; show: (rec: TryRec) => Promise<void> };

const HOOKS: Record<Tab, Hooks> = {
  agents: {
    selection: () => {
      const c = crew.get();
      return c.form ? { agent: c.form.name, ...(dirty(c) || !c.saved ? { unsaved: c.form } : {}) } : {};
    },
    after: (targets) => afterApply(targets.filter((t) => t.startsWith("agent:")).map((t) => t.split(":")[1])),
    show: (rec) => showTry(rec.id),
  },
  workflows: { selection: () => ({}), after: async () => undefined, show: async () => undefined },
};

/** 3.6.0.0 R2: a tab other than Agents says what is open in it and what follows an Apply (routes/crew/flows/flowStore.ts). */
export function onTab(tab: Tab, hooks: Hooks): void {
  HOOKS[tab] = hooks;
}

const key = (tab: Tab) => `halo.studio.builder.${tab}`;
const newCid = (tab: Tab) => `${tab}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

function kept(tab: Tab): { cid: string; msgs: Msg[] } {
  try {
    const got = JSON.parse(localStorage.getItem(key(tab)) || "null");
    if (got && typeof got.cid === "string" && Array.isArray(got.msgs)) return { cid: got.cid, msgs: got.msgs };
  } catch {
    /* a private window keeps nothing */
  }
  return { cid: newCid(tab), msgs: [] };
}

function keep(tab: Tab, cid: string, msgs: Msg[]): void {
  try {
    localStorage.setItem(key(tab), JSON.stringify({ cid, msgs: msgs.slice(-40) }));
  } catch {
    /* nothing kept */
  }
}

const make = (tab: Tab) => createStore<BuilderState>({ ...kept(tab), open: false, text: "", sending: false, pending: [], meta: null, receipt: null, error: "" });
export const builders: Record<Tab, Store<BuilderState>> = { agents: make("agents"), workflows: make("workflows") };
export const builder = builders.agents;
export const useBuilder = <T,>(pick: (s: BuilderState) => T, tab: Tab = "agents"): T => useStore(builders[tab], pick);
const msg = (e: unknown) => (e instanceof ApiError ? e.message : String(e));

function say(tab: Tab, m: Msg): void {
  builders[tab].update((s) => {
    const msgs = [...s.msgs, m];
    keep(tab, s.cid, msgs);
    return { msgs };
  });
}

export async function loadMeta(tab: Tab = "agents"): Promise<void> {
  try {
    const meta = await api.get<Meta>("builder");
    builders[tab].update(() => ({ meta }));
  } catch {
    /* the line beside the box says nothing new */
  }
}

export const setText = (text: string, tab: Tab = "agents") => builders[tab].update(() => ({ text }));
export const toggleOpen = (tab: Tab = "agents") => builders[tab].update((s) => ({ open: !s.open }));

/** "Write it for me": the box, filled, focused; the person sends it. */
export function prefill(text: string, tab: Tab = "agents"): void {
  builders[tab].update(() => ({ text }));
  window.setTimeout(() => (document.querySelector(`[data-builder-tab=${tab}] [data-testid=builder-input]`) as HTMLInputElement | null)?.focus(), 0);
}

export async function send(textIn?: string, tab: Tab = "agents"): Promise<void> {
  const b = builders[tab];
  const s = b.get();
  const text = (textIn ?? s.text).trim();
  if (!text || s.sending) return;
  const selection = HOOKS[tab].selection();
  const history = s.msgs.slice(-8).map((m) => ({ me: !!m.me, text: m.text }));
  say(tab, { me: true, text });
  b.update(() => ({ text: textIn === undefined ? "" : s.text, sending: true, open: true, pending: [], error: "" }));
  try {
    const r = await api.post<{ reply: string; question?: Msg["question"]; changes: Change[]; cost_usd: number; meta: Meta; tries?: TryRec[] }>(
      "builder/ask", { tab, selection, text, conversation_id: s.cid, history });
    say(tab, { text: r.reply, question: r.question, cost: r.cost_usd });
    b.update(() => ({ sending: false, pending: r.changes || [], meta: r.meta || b.get().meta }));
    for (const t of r.tries || []) void HOOKS[tab].show(t);
  } catch (e) {
    const data = e instanceof ApiError ? (e.data as { meta?: Meta } | undefined) : undefined;
    say(tab, { text: msg(e) });
    b.update(() => ({ sending: false, ...(data?.meta ? { meta: data.meta } : {}) }));
  }
}

export function tick(id: string, on: boolean, tab: Tab = "agents"): void {
  builders[tab].update((s) => ({ pending: s.pending.map((c) => (c.id === id ? { ...c, ticked: on } : c)) }));
}

export function discardPreview(tab: Tab = "agents"): void {
  builders[tab].update(() => ({ pending: [] }));
  say(tab, { text: "Discarded: nothing changed." });
}

export async function apply(tab: Tab = "agents"): Promise<void> {
  const b = builders[tab];
  const s = b.get();
  const ids = s.pending.filter((c) => c.ticked).map((c) => c.id);
  if (!ids.length) return discardPreview(tab);
  try {
    const r = await api.post<{ undo_id: string; wrote: string[]; removed: string[]; skipped: string[]; filled: { field: string; value: string }[] }>(
      "builder/apply", { conversation_id: s.cid, change_ids: ids });
    for (const f of r.filled || []) setForm({ [f.field]: f.value });
    const touched = [...new Set(s.pending.filter((c) => ids.includes(c.id)).map((c) => c.target))];
    const n = r.wrote.length + r.removed.length;
    const line = n ? `The builder wrote ${n} file${n > 1 ? "s" : ""}.` : r.filled?.length ? "Put into the form: read it, then Save." : "Nothing to write.";
    say(tab, { text: line + (r.skipped?.length ? ` ${r.skipped.join(" ")}` : "") });
    b.update(() => ({ pending: [], receipt: n ? { line, undo: r.undo_id, touched } : null }));
    await HOOKS[tab].after(touched);
  } catch (e) {
    say(tab, { text: msg(e) });
  }
}

export async function undo(tab: Tab = "agents"): Promise<void> {
  const b = builders[tab];
  const r = b.get().receipt;
  if (!r) return;
  try {
    const got = await api.post<{ restored: string[] }>("builder/undo", { undo_id: r.undo });
    b.update(() => ({ receipt: null }));
    say(tab, { text: `Undone: ${got.restored.length} file${got.restored.length === 1 ? "" : "s"} as before.` });
    await HOOKS[tab].after(r.touched);
  } catch (e) {
    say(tab, { text: msg(e) });
  }
}

/** 3.6.0.0 R2: a proposal's "make it" takes its lines out of the preview (the agent form makes it instead). */
export function untickTarget(target: string, tab: Tab = "workflows"): void {
  builders[tab].update((s) => ({ pending: s.pending.map((c) => (c.target === target ? { ...c, ticked: false } : c)) }));
}

export function newConversation(tab: Tab = "agents"): void {
  const cid = newCid(tab);
  keep(tab, cid, []);
  builders[tab].update(() => ({ cid, msgs: [], pending: [], receipt: null }));
}
