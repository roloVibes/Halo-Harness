// 3.6.0.13 L5: which box rings on the drawing of a running session (Agents -> Live and Session's map), pure: no React, no
// DOM, no store, no clock of its own. A member rings ASK when its raw state turns `waiting`, DONE when it turns `done`
// (never `stopped`), FAILED when it turns `failed`; a group rings HAND when its DRAWN members gain an id and lose none (the
// held geometry's members: a member added while the drawing is held rings when it is laid out again; a group whose
// members were replaced is another drawing, never a hand-out). Nothing on the first draw (`prev` empty) or a re-draw with
// no change; nothing for a box not wholly in view, under the pointer (the box, or the group of the member under it) or
// meeting `cover` (the open step-in card's rect, cover.ts; OP1's sheet is not in this release); a box once per 4 s
// (`last`: when each id last rang, ms); at most four at once, the top-most first. Main's box never rings; no TALK ring.
import type { Rect } from "../../session/downFit";

export type RingKind = "ask" | "done" | "failed" | "hand";
export type RingBox = { id: string; kind: "member" | "group"; raw?: string; members?: string[]; top: number; bottom: number; left: number; right: number };
export type Ring = { id: string; kind: RingKind };
export type RingView = Rect & { pointer: string | null; now: number };

export const RING_GAP_MS = 4000;
export const RINGS_AT_ONCE = 4;
const TURNS: Record<string, RingKind> = { waiting: "ask", done: "done", failed: "failed" };

/** The ring box `b` earns since `p` (its last draw), or null. */
function eventOf(p: RingBox | undefined, b: RingBox): RingKind | null {
  if (b.kind === "member") return p && p.raw !== b.raw ? TURNS[b.raw || ""] || null : null;
  const had = p?.members || [], has = b.members || [];
  return had.every((id) => has.includes(id)) && has.some((id) => !had.includes(id)) ? "hand" : null;
}

const within = (b: RingBox, v: Rect) => b.top >= v.top && b.bottom <= v.bottom && b.left >= v.left && b.right <= v.right;
const meets = (b: RingBox, c: Rect) => b.top < c.bottom && b.bottom > c.top && b.left < c.right && b.right > c.left;
const pointed = (b: RingBox, pointer: string | null) => !!pointer && (b.id === pointer || !!b.members?.includes(pointer));

export function ringEvents(prev: RingBox[], next: RingBox[], view: RingView, cover: Rect | null, last: Record<string, number>): Ring[] {
  if (!prev.length) return [];
  const before = new Map(prev.map((b) => [b.id, b]));
  const out: (Ring & { top: number; left: number })[] = [];
  for (const b of next) {
    const kind = eventOf(before.get(b.id), b);
    if (!kind || !within(b, view) || pointed(b, view.pointer) || (cover && meets(b, cover))) continue;
    if (last[b.id] != null && view.now - last[b.id] < RING_GAP_MS) continue;
    out.push({ id: b.id, kind, top: b.top, left: b.left });
  }
  return out.sort((a, b) => a.top - b.top || a.left - b.left).slice(0, RINGS_AT_ONCE).map(({ id, kind }) => ({ id, kind }));
}
