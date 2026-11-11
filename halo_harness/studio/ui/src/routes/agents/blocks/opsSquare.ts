// A square block's own writes (3.3.16.3): who is inside it (PUT workflows/members: a square of yours in place, a shipped
// one copied to yours first and the board swapped to the copy), its "when" (PUT workflows/when: the lineup's item, or
// config on the auto lineup), its line from main (connect = the plain rule, its covers), and its spot on the canvas
// (the lineup's layout, `block:<ref>`). Each joins Undo / Redo and says what changed in one line.
import { api } from "../../../lib/api";
import { roles } from "../../roles/store";
import { movePositions } from "../../roles/sync";
import type { Pos } from "../../roles/types";
import { boardLineup, loadBoard, squareOf, wf, type Square } from "../workflows/store";
import { pushStep } from "./history";
import { ask, say } from "./note";
import { coversLabel, writesBoard } from "./templates";

type Got = { ok: boolean; line: string; ref?: string; copied_from?: string };
type When = { needs?: string[]; words?: string[]; mode?: string };

const on = () => (boardLineup() ? { lineup: boardLineup() } : {});
async function put(path: string, body: object): Promise<Got> {
  return api.put<Got>(path, { ...body, ...on() });
}
const fileOf = (q: Square) => (q.writable ? q.path.split(/[\\/]/).slice(-2).join("/") : `a copy of ${q.ref} in yours (my-${q.ref.split("/").pop()}.yaml): ${q.ref} is ${q.group === "packs" ? "a pack's" : "shipped"}, so it is copied first and main's line moves to the copy`);

async function members(ref: string, change: { add?: string; remove?: string }): Promise<Got> {
  return put("workflows/members", { ref, ...change });
}

/** (b) An agent into a square: a library bio, a tier card (it stays in its tier), or another square's agent (it leaves that one). */
export function offerJoin(ref: string, bio: string, from = ""): void {
  const q = squareOf(wf.get(), ref);
  if (!q) return;
  if (from === ref) return;
  ask({ kind: "join", button: "Add it", title: `Add ${bio} to ${ref}?`,
        what: `${bio} joins ${ref}'s agents on an auto model (picked per task)${from ? `; it leaves ${from}` : ""}`,
        costs: `nothing now; ${ref}'s hand-offs stay ${q.costs}`, writes: fileOf(q) + (from ? `, and ${from}'s file` : ""),
        go: async () => {
          const got = await members(ref, { add: bio });
          const into = got.ref || ref;
          if (from) await members(from, { remove: bio });
          await loadBoard();
          say(got.line + (from ? `; it left ${from}` : ""));
          pushStep(`${bio} joined ${into}`, async () => {
            const back = await members(into, { remove: bio });
            if (from) await members(from, { add: bio });
            if (got.copied_from) await api.post("workflows/swap", { from: into, to: got.copied_from, ...on() });
            await loadBoard();
            return back.line + (got.copied_from ? `; ${got.copied_from} is back on the board (the copy stays in yours)` : "");
          }, async () => {
            if (got.copied_from) await api.post("workflows/swap", { from: got.copied_from, to: into, ...on() });
            const again = await members(into, { add: bio });
            if (from) await members(from, { remove: bio });
            await loadBoard();
            return again.line;
          });
        } });
}

/** (c) An agent out of a square onto the empty canvas: it leaves (the last one cannot: the block's x takes it off). */
export function offerLeave(ref: string, bio: string): void {
  const q = squareOf(wf.get(), ref);
  if (!q) return;
  ask({ kind: "leave", button: "Take it out", title: `Take ${bio} out of ${ref}?`, what: `${bio} leaves ${ref}; the bio itself stays`,
        costs: "nothing", writes: fileOf(q), go: () => leave(ref, bio) });
}

/** The leave itself (the confirm card's, or the Agents page's ask after Delete); joins Undo. */
export async function leave(ref: string, bio: string): Promise<void> {
  const got = await members(ref, { remove: bio });
  const from = got.ref || ref;
  await loadBoard();
  say(got.line);
  pushStep(`${bio} left ${from}`, async () => {
    const back = await members(from, { add: bio });
    if (got.copied_from) await api.post("workflows/swap", { from, to: got.copied_from, ...on() });
    await loadBoard();
    return back.line;
  }, async () => {
    if (got.copied_from) await api.post("workflows/swap", { from: got.copied_from, to: from, ...on() });
    const again = await members(from, { remove: bio });
    await loadBoard();
    return again.line;
  });
}

export const leaveWrites = (q: Square): string => fileOf(q);

/** A block's "when", written (the When page's Save, a Disconnect, a connect); its Undo writes the rule before it back. */
export async function setWhen(ref: string, when: When, label = "the rule"): Promise<string> {
  const q = squareOf(wf.get(), ref);
  const was: When = q?.when || {};
  const got = await put("workflows/when", { ref, when });
  await loadBoard();
  say(got.line);
  pushStep(`${ref}: ${label}`, async () => {
    const back = await put("workflows/when", { ref, when: was });
    await loadBoard();
    return back.line;
  }, async () => {
    const again = await put("workflows/when", { ref, when });
    await loadBoard();
    return again.line;
  });
  return got.line;
}

/** A line drawn from main to a block (its edge handle dragged onto it, or "Connect to main" in the block's menu). */
export function offerConnect(ref: string): void {
  const q = squareOf(wf.get(), ref);
  if (!q) return;
  if (q.when_mode !== "off") return say(`${ref} is connected already: click its line to change when`);
  ask({ kind: "connect", button: "Connect", title: `Connect main to ${ref}?`,
        what: `main hands ${ref} work when main ${coversLabel(q.covers)} (its covers; click the line after to narrow it)`,
        costs: `nothing now; each hand-off: ${q.costs}`, writes: writesBoard().replace("workflows.enabled", "workflows.when"),
        go: async () => void (await setWhen(ref, {}, "connected to main")) });
}

/** (d) A block moved by its title bar: its spot in the lineup's layout (`block:<ref>`), with Undo. */
export function moveBlock(ref: string, from: Pos | undefined, to: Pos): void {
  const key = `block:${ref}`;
  movePositions({ [key]: to });
  say(`${ref} moved (saved in lineup ${roles.get().name}'s layout)`);
  pushStep(`${ref} moved`, async () => {
    if (from) movePositions({ [key]: from });
    else roles.update((s) => ({ positions: Object.fromEntries(Object.entries(s.positions).filter(([k]) => k !== key)) })), movePositions({});
    return `${ref} is back where it was`;
  }, async () => (movePositions({ [key]: to }), `${ref} moved again`));
}
