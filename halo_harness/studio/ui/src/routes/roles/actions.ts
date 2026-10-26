// What the Roles editor does to a lineup (3.0.7.0 R2): every edit goes
// through `edit` (the mapping before it joins the undo history, the Problems
// panel re-validates), Ctrl+Z / Ctrl+Shift+Z walk that history, Save is
// `PUT lineup/<name>` (a shipped lineup saves as your copy; a 422 lists the
// validator's lines in the Inspector; 3.2.0.0 R2: a pack's lineup is
// read-only, Customize makes your copy), and New, Duplicate, Delete and Apply
// are the lineup routes. A card dropped into another tier box rewrites
// `tiers[*].members` and saves at once; the main agent stays in tier 0.
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { agentsOf, clone, closeDialog, HISTORY_MAX, keyOf, nodeById, packOf, readOnlySource, roles } from "./store";
import { carryLayout, loadLists, movePositions, msg, openLineup, rekeyPositions, validateSoon, type LayoutBody } from "./sync";
import type { Graph, LineupPayload, Pos, Raw } from "./types";

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

/** 3.2.0.0 R2: a pack's lineup is read-only on the canvas: an edit or a save says so (Customize makes your copy). */
function packLocked(): boolean {
  const s = roles.get();
  const pack = s.current?.pack || packOf(s.current?.scope);
  if (pack) toast(`${s.name} is from pack ${pack}, read-only: Customize makes your copy to edit`, "info", 3500);
  return !!pack;
}

/** One edit of the open lineup: `fn` changes a copy; the old mapping joins the undo history. */
export function edit(fn: (raw: Raw) => void): void {
  const s = roles.get();
  if (!s.raw || packLocked()) return;
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

/** Save the open lineup to your scope (a shipped or a pack's one becomes your copy under the same name). 3.3.0.0 R7:
 *  the card positions ride in the same `PUT lineup` (carryLayout: a pending move goes with it, never a PUT racing it). */
export async function save(): Promise<boolean> {
  const s = roles.get();
  if (!s.raw || !s.name || !s.current || packLocked()) return false;
  return carryLayout((layout) => saveWith(layout));
}

async function saveWith(layout: LayoutBody | null): Promise<boolean> {
  const s = roles.get();
  if (!s.raw || !s.name || !s.current) return false;
  const query = { scope: s.scope, duplicate: readOnlySource(s.current.scope) ? "1" : "" };
  roles.update(() => ({ busy: "save" }));
  try {
    const sent = s.raw;
    const p = await api.put<LineupPayload>("lineup/" + encodeURIComponent(s.name), layout ? { raw: s.raw, layout } : { raw: s.raw }, query);
    // an edit or an undo that landed while the save was in flight stays: only an unchanged mapping takes the saved copy
    const untouched = roles.get().raw === sent;
    roles.update((st) => ({ current: p, graph: p.graph, positions: rekeyPositions(st.graph, p.graph, st.positions), findings: p.findings || [], saveProblems: [],
                          ...(untouched ? { raw: clone(p.raw), dirty: false } : { dirty: true }) }));
    toast(`${p.name} saved to ${p.scope} scope`, "done");
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

/** The graph with card `id` in tier `name` (drawn so until the save's answer brings the server's graph). */
const withTier = (g: Graph, id: string, name: string): Graph => ({
  ...g,
  tiers: g.tiers.map((t) => ({ ...t, node_ids: t.name === name ? [...t.node_ids.filter((k) => k !== id), id] : t.node_ids.filter((k) => k !== id) })),
});

/** A card dropped into another tier box: its alias moves to that tier's members, and the lineup saves. 3.3.0.0 R7:
 *  one ordered write -- `patch` (the drop's positions, clamped into the target box from the boxes as they are at
 *  the drop) is in the store at once with the card in its new tier, and the lineup save carries it (the server
 *  writes the lineup and the layout in one request); a refused move puts both back. */
export async function moveToTier(nodeId: string, tier: string, patch: Record<string, Pos> = {}): Promise<boolean> {
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
  const before = roles.get().raw;
  edit((raw) => {
    const list = (Array.isArray(raw.tiers) ? raw.tiers : []) as { name: string; members: string[] }[];
    for (const t of list) t.members = (Array.isArray(t.members) ? t.members : []).filter((m) => m !== key);
    const target = list.find((t) => t.name === to.name);
    if (target) target.members.push(key);
    raw.tiers = list;
  });
  if (roles.get().raw === before) return false; // nothing changed (a pack's lineup: read-only)
  const was = Object.fromEntries(Object.keys(patch).map((k) => [k, s.positions[k]]));
  roles.update((st) => ({ positions: { ...st.positions, ...patch }, graph: st.graph && withTier(st.graph, nodeId, to.name) }));
  const ok = await save();
  if (ok) toast(`${key} is in tier ${to.index} (${to.name}) now`, "done");
  else {
    undo();
    roles.update((st) => {
      const back = { ...st.positions };
      for (const [k, p] of Object.entries(patch)) if (st.positions[k] === p) (was[k] ? (back[k] = was[k]) : delete back[k]);
      return { positions: back, graph: st.graph && withTier(st.graph, nodeId, from.name) };
    });
    movePositions({}); // the spots put back go to the file too (the save's own layout write did not happen)
  }
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
