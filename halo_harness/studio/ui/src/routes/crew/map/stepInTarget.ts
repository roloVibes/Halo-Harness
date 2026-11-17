// Who a click in a run's drawing steps in on (3.6.0.2 R18), read from the session's ROWS at the click, never from frames:
// - a box: its live rows (its one live child, else a row per live child, each with its own buttons);
// - a step row of a workflow's block: its tagged child (`crew.workflow` + `crew.step`); the block's head: the running step's;
// - a line: the live child carrying that `crew.line` (a line to `workflow:{W}`: the running step's child; to
//   `made-up:{aid}`: that child);
// - nothing live (a done or next row, a line nobody travels now): the state only (`who` is empty).
// The caller gives the words of what was clicked (`text`: the row's own words, the box's "kind · state", the line's trace
// or "Starts when"); an off-map line also names its sender (R18: "Open the map at {sender}"). Shared by Session's Live
// drawer and Agents' Live view: no Session import.
import type { OvRow, Overlay } from "./overlay";
import { runningStep } from "./overlayBlocks";

export type Hit =
  | { kind: "box"; box: string; name: string; text: string }
  | { kind: "step"; workflow: string; n: number; text: string }
  | { kind: "head"; workflow: string; text: string }
  | { kind: "line"; from: string; to: string; text: string; off: boolean };
/** One agent row of the session (lib/work/record.ts RecordAgent's fields this needs). */
export type RecRow = { id: string; key: string; name: string; state: string; row: OvRow };
/** One agent the card speaks to: its fleet key `hid|sid|aid`, its agent id, its words. */
export type Who = { key: string; aid: string; name: string };
export type Target = { id: string; title: string; text: string; who: Who[]; sender: string };

const LIVE = ["queued", "running", "waiting", "paused"];
const isLive = (a: RecRow) => LIVE.includes(String(a.state || ""));
export const who = (a: RecRow): Who => ({ key: a.key, aid: a.id, name: String(a.row.crew?.agent || a.name || a.id) });
const newest = (rs: RecRow[]): RecRow | undefined => rs[rs.length - 1];

/** The live child of the workflow `w`'s step `n` (no `n`: the running step's, else any live step child). */
function stepChild(w: string, n: number | undefined, rows: RecRow[]): RecRow | undefined {
  const tagged = rows.filter((a) => a.row.crew?.workflow === w);
  return newest(tagged.filter((a) => isLive(a) && (n == null || Number(a.row.crew?.step) === n)));
}

/** The id a click is known by (a second click on the same thing closes the card). */
export const hitId = (h: Hit): string =>
  h.kind === "box" ? `box:${h.box}` : h.kind === "step" ? `step:${h.workflow}:${h.n}` : h.kind === "head" ? `head:${h.workflow}` : `line:${h.from}>${h.to}`;

export function stepIn(h: Hit, rows: RecRow[], ov: Overlay | null): Target {
  const base = { id: hitId(h), text: h.text, sender: "" };
  if (h.kind === "box") {
    const ids = new Set([...(ov?.kids[h.box] || []).map((k) => k.aid), ...(ov?.boxes[h.box]?.agents || [])]);
    const live = rows.filter((a) => ids.has(a.id) && isLive(a));
    return { ...base, title: live.length === 1 ? who(live[0]).name : h.name, who: live.map(who) };
  }
  if (h.kind === "step" || h.kind === "head") {
    const lit = ov?.blocks[h.workflow];
    const n = h.kind === "step" ? h.n : lit ? runningStep(lit) : undefined;
    const calm = ["done", "next"].includes(lit?.steps.find((x) => x.n === n)?.state || ""); // a done or next row: the state only
    const a = calm || (h.kind === "head" && n == null) ? undefined : stepChild(h.workflow, n, rows);
    return { ...base, title: a ? who(a).name : `workflow ${h.workflow}`, who: a ? [who(a)] : [] };
  }
  let a: RecRow | undefined;
  if (h.to.startsWith("workflow:")) {
    const w = h.to.slice("workflow:".length), lit = ov?.blocks[w];
    a = stepChild(w, lit ? runningStep(lit) : undefined, rows) || stepChild(w, undefined, rows);
  } else if (h.to.startsWith("made-up:")) a = rows.find((r) => r.id === h.to.slice("made-up:".length) && isLive(r));
  else a = newest(rows.filter((r) => isLive(r) && r.row.crew?.line === `${h.from} -> ${h.to}`));
  return { ...base, title: a ? who(a).name : `${h.from} -> ${h.to}`, who: a ? [who(a)] : [], sender: h.off ? h.from : "" };
}

/** Where agent `aid` is drawn: the box its row belongs to, else its workflow's block. Pure (tests/test_studio_door_kept.py; askBox.ts uses it). */
export function placeOf(aid: string, ov: Overlay | null, rows: RecRow[]): { box?: string; workflow?: string } | null {
  if (aid === "main") return { box: "main" };
  if (!ov) return null;
  for (const [id, b] of Object.entries(ov.boxes)) if (b.agents.includes(aid)) return { box: id };
  for (const [id, ks] of Object.entries(ov.kids)) if (ks.some((k) => k.aid === aid)) return { box: id };
  const w = rows.find((r) => r.id === aid)?.row.crew?.workflow;
  return w ? { workflow: w } : null;
}
