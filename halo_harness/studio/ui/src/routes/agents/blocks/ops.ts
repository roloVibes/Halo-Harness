// What a block drop does (3.3.16.3, docs/STUDIO-blocks.md "Drag and drop"): each drop that writes first raises the
// confirm card (WHAT it adds, what it COSTS, what it WRITES), then makes the write through the routes that already own
// those files -- workflows/enable | disable, workflows/templates/*, workflows/members, workflows/swap (a square of
// yours or config), the lineup's own save (PUT lineup, the canvas's mapping) -- says what changed in one line and joins
// Undo / Redo. A shipped square is copied to yours before it changes, and the card says so first.
import { api } from "../../../lib/api";
import { edit, save } from "../../roles/actions";
import { roles } from "../../roles/store";
import type { Raw } from "../../roles/types";
import { boardLineup, loadBoard, squareOf, wf } from "../workflows/store";
import { markSaved, pushStep } from "./history";
import { ask, say } from "./note";
import { coversLabel, writesBoard, type Template } from "./templates";

type Got = { ok: boolean; line: string; ref?: string; copied_from?: string; raw?: Raw; tier?: string };

const on = () => (boardLineup() ? { lineup: boardLineup() } : {});
async function call(method: "post" | "put", path: string, body: object, reload = true): Promise<Got> {
  const got = await api[method]<Got>(path, { ...body, ...on() });
  if (reload) await loadBoard();
  return got;
}
const where = () => wf.get().board?.where || "this lineup";

/** (a) A workflow from the library onto the canvas. */
export function offerWorkflow(ref: string): void {
  const s = wf.get();
  const q = squareOf(s, ref);
  if (!q) return;
  if (s.board?.enabled.includes(ref)) return say(`${ref} is on the board already`);
  ask({ kind: "workflow", button: "Add it", title: `Add ${ref} to ${where()}?`,
        what: `the ${ref} block -- ${q.does || "a square"} -- wired to main: when main ${coversLabel(q.covers)}`,
        costs: `nothing now; each hand-off: ${q.costs}`, writes: writesBoard(),
        go: async () => {
          const got = await call("post", "workflows/enable", { ref });
          say(got.line);
          pushStep(`${ref} added`, async () => (await call("post", "workflows/disable", { ref })).line,
                   async () => (await call("post", "workflows/enable", { ref })).line);
        } });
}

/** (a) A block template from the library onto the canvas: a square of yours, or a tier in the lineup. */
export function offerTemplate(t: Template): void {
  const who = t.agents.map((a) => a.bio).join(", ");
  if (t.kind === "tier") return offerTier(t, who);
  ask({ kind: "template", button: "Add it", title: `Add the block "${t.title}"?`,
        what: `${t.as}: ${t.does} Inside: ${who}, each on auto (pin models after). Wired to main: when main ${coversLabel(t.covers)}`,
        costs: `nothing now; each hand-off: ${t.costs}`,
        writes: `a new square of yours, ~/.halo/workflows/${t.as}.yaml (the template stays as shipped), and ${writesBoard()}`,
        go: async () => {
          const got = await call("post", "workflows/templates/add", { template: t.name });
          say(got.line);
          const ref = got.ref || t.as;
          pushStep(`${ref} added`, async () => (await call("post", "workflows/templates/remove", { ref })).line,
                   async () => (await call("post", "workflows/templates/add", { template: t.name, as: ref })).line);
        } });
}

function offerTier(t: Template, who: string): void {
  const s = roles.get();
  const shipped = s.current?.scope === "template";
  ask({ kind: "template", button: "Add it", title: `Add the tier block "${t.title}"?`,
        what: `a tier below the last one with ${who}, each on auto: ${t.does}`, costs: "nothing now; your models, picked per task",
        writes: `lineup ${s.name}'s file: ${t.agents.length} agents, the tier and its routing words${shipped ? " (it is shipped: Save makes your copy, as every Cast edit does)" : ""}`,
        go: async () => {
          const got = await api.post<Got>("workflows/templates/merge", { template: t.name, raw: roles.get().raw || {} });
          await lineupWrite((raw) => replace(raw, got.raw || {}), `tier ${got.tier} added with ${who}`);
        } });
}

function replace(raw: Raw, next: Raw): void {
  for (const k of Object.keys(raw)) delete raw[k];
  Object.assign(raw, JSON.parse(JSON.stringify(next)));
}

/** A lineup change a block op makes: one edit, saved at once; its Undo saves too (history.ts markSaved). */
export async function lineupWrite(fn: (raw: Raw) => void, line: string): Promise<void> {
  const before = roles.get().raw;
  edit(fn);
  if (roles.get().raw === before) throw new Error(`${roles.get().name} is read-only here: Customize makes your copy`);
  markSaved(roles.get().raw);
  if (!(await save())) throw new Error("the lineup did not save (Problems says why)");
  markSaved(roles.get().raw); // the save put the server's copy in its place: that one is what Undo walks back from
  say(`${line}: saved lineup ${roles.get().name}`);
}

/** (b) A bio (from the library, a tier card, or another square) into a tier: a card in that tier. */
export function offerIntoTier(tier: string, bio: string, from = ""): void {
  const name = roles.get().name;
  ask({ kind: "join", button: "Add it", title: `Add ${bio} to tier ${tier}?`,
        what: `a ${bio} card in tier ${tier}, on its bio's model${from ? ` (it stays in ${from} too)` : ""}`,
        costs: "nothing now; it runs when main hands its tier work", writes: `lineup ${name}'s file (agents, tiers)`,
        go: () => lineupWrite((raw) => joinTier(raw, tier, bio), `${bio} joined tier ${tier}`) });
}

function joinTier(raw: Raw, tier: string, bio: string): void {
  const agents = (Array.isArray(raw.agents) ? raw.agents : (raw.agents = [])) as Raw[];
  const taken = new Set(agents.map((a) => String(a.as || a.role || "")));
  const base = bio.replace(/^auto-/, "");
  let alias = base, n = 2;
  while (taken.has(alias)) alias = `${base}-${n++}`;
  agents.push({ agent: bio, role: "custom", as: alias });
  const t = ((raw.tiers || []) as Raw[]).find((x) => x.name === tier);
  if (t) t.members = [...((t.members as string[]) || []), alias];
}

