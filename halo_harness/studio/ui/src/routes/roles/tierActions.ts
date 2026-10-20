// The tier edits of the Roles canvas (3.1.6.0 R1; the owner: "how do I create
// custom tiers to then put models and agents in new tiers? ... That should be
// much easier to add in the canvas"): Add tier (the canvas bar's name field;
// with no declared tiers it first declares tier 0 = the main card alone, then
// the new tier, empty), rename (the box head, in place), and the box menu's
// Model, Trigger, Max parallel and Delete (its cards fall to the implicit
// last tier; tier 0 stays). Each is one `edit` (Ctrl+Z undoes it) and then a
// Save, like a card dropped into another box (`moveToTier`).
import { toast } from "../../lib/store";
import { edit, save, undo } from "./actions";
import { keyOf, roles } from "./store";
import { setCollapsed } from "./sync";
import type { Raw, TierTrigger } from "./types";

type TierRaw = { name: string; members: string[]; model?: string; trigger?: TierTrigger; max_parallel?: number; [k: string]: unknown };

export const TOP_TIER = "top";

const listOf = (raw: Raw | null): TierRaw[] => (raw && Array.isArray(raw.tiers) ? (raw.tiers as TierRaw[]) : []);

/** Why `name` cannot name a tier (`except`: the tier being renamed), or "". */
export function tierNameProblem(name: string, except = ""): string {
  const n = name.trim();
  if (!n) return "a tier needs a name";
  const s = roles.get();
  const taken = [...(s.graph?.tiers || []).map((t) => t.name), ...listOf(s.raw).map((t) => t.name)].some((t) => t === n && t !== except);
  return taken ? `this lineup already has a tier named ${n}` : "";
}

/** One edit of `tiers`, then Save; a save that fails is undone (the toast says why). */
async function commit(fn: (list: TierRaw[]) => void, done: string): Promise<boolean> {
  const before = roles.get().raw;
  edit((raw) => {
    const list = listOf(raw);
    fn(list);
    raw.tiers = list;
  });
  if (roles.get().raw === before) return true;
  const ok = await save();
  if (ok) toast(done, "done");
  else undo();
  return ok;
}

function patchTier(name: string, fn: (t: TierRaw) => void, done: string): Promise<boolean> {
  return commit((list) => {
    const t = list.find((x) => x.name === name);
    if (t) fn(t);
  }, done);
}

/** Add tier: a new, empty box after the last declared tier (tier 0 = main alone first, when none is declared). */
export async function addTier(name: string): Promise<boolean> {
  const n = name.trim();
  const problem = tierNameProblem(n);
  if (problem) return toast(problem, "error", 4000), false;
  const main = roles.get().graph?.nodes.find((x) => x.role === "main");
  const ok = await commit((list) => {
    if (!list.length && main) list.push({ name: n === TOP_TIER ? "lead" : TOP_TIER, members: [keyOf(main)] });
    list.push({ name: n, members: [] });
  }, `Tier ${n} added: drag cards into its box (Ctrl+Z takes it back)`);
  if (ok) roles.update(() => ({ tierAdd: false }));
  return ok;
}

/** The box head's rename (Enter keeps it); the collapsed state follows the name. */
export async function renameTier(from: string, to: string): Promise<boolean> {
  const n = to.trim();
  roles.update(() => ({ tierRename: "" }));
  if (!n || n === from) return true;
  const problem = tierNameProblem(n, from);
  if (problem) return toast(problem, "error", 4000), false;
  const folded = !!roles.get().collapsed[from];
  const ok = await patchTier(from, (t) => void (t.name = n), `Tier ${from} is ${n} now`);
  if (ok && folded) setCollapsed(n, true);
  return ok;
}

/** The tier's own model ("" = none: its members run on their bios' models, a `default` bio on the session's). */
export function setTierModel(name: string, ref: string): Promise<boolean> {
  return patchTier(name, (t) => {
    if (ref) t.model = ref;
    else delete t.model;
  }, ref ? `Tier ${name}'s members run on ${ref} (a card's own model, or a bio that pins one, still wins)` : `Tier ${name} names no model now`);
}

/** The tier's trigger (null = none). */
export function setTierTrigger(name: string, trigger: TierTrigger | null): Promise<boolean> {
  return patchTier(name, (t) => {
    if (trigger) t.trigger = trigger;
    else delete t.trigger;
  }, trigger ? `Tier ${name}'s trigger starts its lead while a session on this lineup runs` : `Tier ${name} has no trigger now`);
}

/** How many of the tier's members run at once (null = no cap). */
export function setTierMax(name: string, n: number | null): Promise<boolean> {
  return patchTier(name, (t) => {
    if (n && n >= 1) t.max_parallel = Math.floor(n);
    else delete t.max_parallel;
  }, n ? `Tier ${name} runs at most ${Math.floor(n)} at once` : `Tier ${name} has no cap now`);
}

/** Delete a tier: its cards fall to the implicit last tier. Tier 0 stays. */
export async function deleteTier(name: string): Promise<boolean> {
  const i = listOf(roles.get().raw).findIndex((t) => t.name === name);
  if (i < 0) return false;
  if (i === 0) return toast(`Tier 0 (${name}) holds the main agent: it stays`, "error", 4000), false;
  return commit((list) => void list.splice(i, 1), `Tier ${name} deleted: its cards are in the last tier now (Ctrl+Z puts it back)`);
}
