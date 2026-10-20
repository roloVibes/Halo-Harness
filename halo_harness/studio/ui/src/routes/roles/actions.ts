// What the Roles editor does to a lineup (3.0.7.0 R2): every edit goes
// through `edit` (the mapping before it joins the undo history, the Problems
// panel re-validates), Ctrl+Z / Ctrl+Shift+Z walk that history, Save is
// `PUT lineup/<name>` (a shipped lineup saves as your copy; a 422 lists the
// validator's lines in the Inspector), and New, Duplicate, Delete and Apply
// are the lineup routes. A card dropped into another tier box rewrites
// `tiers[*].members` and saves at once; the main agent stays in tier 0.
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { agentsOf, clone, closeDialog, HISTORY_MAX, keyOf, nodeById, roles, shipped } from "./store";
import { loadLists, msg, openLineup, saveLayout, validateSoon } from "./sync";
import type { LineupPayload, Raw } from "./types";

export async function run<T>(busy: string, fn: () => Promise<T>, done?: (r: T) => string): Promise<T | null> {
  roles.update(() => ({ busy }));
  try {
    const r = await fn();
    if (done) toast(done(r), "done");
    return r;
  } catch (e) {
    toast(msg(e), "error", 5000);
    return null;
  } finally {
    roles.update(() => ({ busy: "" }));
  }
}

/** One edit of the open lineup: `fn` changes a copy; the old mapping joins the undo history. */
export function edit(fn: (raw: Raw) => void): void {
  const s = roles.get();
  if (!s.raw) return;
  const next = clone(s.raw);
  fn(next);
  if (JSON.stringify(next) === JSON.stringify(s.raw)) return;
  roles.update(() => ({ raw: next, past: [...s.past, s.raw!].slice(-HISTORY_MAX), future: [], dirty: true }));
  validateSoon();
}

export function undo(): boolean {
  const s = roles.get();
  if (!s.raw || !s.past.length) return false;
  const prev = s.past[s.past.length - 1];
  roles.update(() => ({ raw: prev, past: s.past.slice(0, -1), future: [s.raw!, ...s.future].slice(0, HISTORY_MAX), dirty: true }));
  validateSoon(true);
  toast("Undone (Ctrl+Shift+Z redoes it)", "info", 1800);
  return true;
}

export function redo(): boolean {
  const s = roles.get();
  if (!s.raw || !s.future.length) return false;
  const [next, ...rest] = s.future;
  roles.update(() => ({ raw: next, past: [...s.past, s.raw!].slice(-HISTORY_MAX), future: rest, dirty: true }));
  validateSoon(true);
  toast("Redone", "info", 1800);
  return true;
}

/** Save the open lineup to your scope (a shipped one becomes your copy under the same name). */
export async function save(): Promise<boolean> {
  const s = roles.get();
  if (!s.raw || !s.name || !s.current) return false;
  const query = { scope: s.scope, duplicate: shipped(s.current.scope) ? "1" : "" };
  roles.update(() => ({ busy: "save" }));
  try {
    const sent = s.raw;
    const p = await api.put<LineupPayload>("lineup/" + encodeURIComponent(s.name), { raw: s.raw }, query);
    // an edit or an undo that landed while the save was in flight stays: only an unchanged mapping takes the saved copy
    const untouched = roles.get().raw === sent;
    roles.update(() => ({ current: p, graph: p.graph, findings: p.findings || [], saveProblems: [],
                          ...(untouched ? { raw: clone(p.raw), dirty: false } : { dirty: true }) }));
    toast(`${p.name} saved to ${p.scope} scope`, "done");
    await saveLayout();
    await loadLists();
    return true;
  } catch (e) {
    const lines = e instanceof ApiError && e.problems.length ? e.problems : [msg(e)];
    roles.update(() => ({ saveProblems: lines }));
    toast(`Not saved: ${lines[0]}`, "error", 5000);
    return false;
  } finally {
    roles.update(() => ({ busy: "" }));
  }
}

export async function applyLineup(): Promise<void> {
  const name = roles.get().name;
  const r = await run("apply", () => api.post<{ notes: string[]; active_team: string }>(`lineup/${encodeURIComponent(name)}/apply`), () => `${name} is the active lineup: new sessions use it`);
  if (r) {
    (r.notes || []).forEach((n) => toast(n, "info", 5000));
    closeDialog();
    await loadLists();
  }
}

export async function newLineup(name: string, from: string): Promise<boolean> {
  const s = roles.get();
  const r = await run("new", () => api.post<LineupPayload>("lineup", { name: name.trim(), from: from || "balanced" }, { scope: s.scope }), (p) => `${p.name} created`);
  if (!r) return false;
  closeDialog();
  await loadLists();
  await openLineup(r.name, true);
  roles.update(() => ({ view: "auto" }));
  return true;
}

export async function deleteLineup(name: string): Promise<void> {
  const r = await run("delete", () => api.del("lineup/" + encodeURIComponent(name), { scope: roles.get().scope }), () => `${name} deleted`);
  if (r === null) return;
  closeDialog();
  if (roles.get().name === name) roles.update(() => ({ name: "", current: null, raw: null, graph: null, findings: [], dirty: false, past: [], future: [], sel: "" }));
  await loadLists();
}

// -- the canvas's edits -------------------------------------------------------------
const MAIN_RULE = "the main agent sits alone in the first tier, and only it";

/** A card dropped into another tier box: its alias moves to that tier's members, and the lineup saves. */
export async function moveToTier(nodeId: string, tier: string): Promise<boolean> {
  const s = roles.get();
  const n = nodeById(s, nodeId);
  const tiers = s.graph?.tiers || [];
  const to = tiers.find((t) => t.name === tier);
  const from = tiers.find((t) => t.node_ids.includes(nodeId));
  if (!n || !to || !from || from.name === to.name) return false;
  if (n.role === "main") return toast(`${keyOf(n)} stays in tier 0 (${from.name}): ${MAIN_RULE}`, "error", 5000), false;
  if (to.index === 0 && tiers.some((t) => t.index === 0 && !t.implicit)) return toast(`Tier 0 (${to.name}) holds the main agent alone: ${keyOf(n)} goes in a tier below it`, "error", 5000), false;
  if (from.implicit && to.implicit) return false;
  const key = keyOf(n);
  edit((raw) => {
    const list = (Array.isArray(raw.tiers) ? raw.tiers : []) as { name: string; members: string[] }[];
    for (const t of list) t.members = (Array.isArray(t.members) ? t.members : []).filter((m) => m !== key);
    const target = list.find((t) => t.name === to.name);
    if (target) target.members.push(key);
    raw.tiers = list;
  });
  const ok = await save();
  if (ok) toast(`${key} is in tier ${to.index} (${to.name}) now`, "done");
  else undo();
  return ok;
}

export function removeCard(nodeId: string): void {
  const n = nodeById(roles.get(), nodeId);
  if (!n) return;
  edit((raw) => {
    agentsOf(raw).splice(n.index, 1);
  });
  roles.update(() => ({ sel: "", dialog: null }));
  toast(`${keyOf(n)} removed (Ctrl+Z puts it back; Save keeps it)`, "info");
}

export function addCard(bio: string, role = "subagent"): void {
  edit((raw) => {
    const agents = agentsOf(raw);
    if (!Array.isArray(raw.agents)) raw.agents = agents;
    (raw.agents as Raw[]).push({ agent: bio, role: role === "main" && agents.some((e) => e.role === "main") ? "subagent" : role });
  });
}
