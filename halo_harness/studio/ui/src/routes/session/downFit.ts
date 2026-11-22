// Session's Live drawer at rest (3.6.0.2 R11, R12): pure arithmetic over the laid-out boxes (world px) and the zoom.
// - `viewHeight`: the scroll box is min(room, bottom of the last whole row + 12) tall, counted from the row at its top,
//   so no box is ever cut by its bottom edge; a box that does not fit waits wholly below it.
// - `belowCount`: the boxes wholly below the scroll box ("↓ {n} more below"); `nextTop`: one row down (the slot's press).
// - `firstSeen` / `keepSeen`: after a hand scroll, the first box he sees keeps its place when the drawing changes.
// - `workingBelow` (3.6.0.5 B26): on Auto, the working group out of sight that the slot names.
// - r/batch04: on Auto the scroll box is the whole room (`drawingHeight`) and the slot names a working group not wholly in
//   view below (`slotOf`); a map of his keeps `viewHeight` and its slot as before.
// - 3.6.0.13 L4: first a group that waits on him out of sight (`waitSlot`), the other groups wholly below (`groupsBelow`),
//   and what a press does while the step-in card is open (`slotPress`, R4: fold first, then scroll).
// No React, no DOM: node runs it (tests/test_studio_session_map_down.py, tests/test_map_groups.py).
import { rawOf } from "../crew/map/groupWords";
import type { PlacedDown } from "../crew/map/layoutDown";
import type { AutoGroup } from "../crew/map/overlayGroups";

export const PAD = 12; // the drawing's top and bottom pad (layoutDown's), and what is kept under the last whole row

export type Placed = { id: string; y: number; h: number };
export type RowBand = { top: number; bottom: number };

/** The rows of a drawing, top to bottom: boxes that share a top (within half a px) are one row. */
export function rowsOf(boxes: Placed[]): RowBand[] {
  const rows: RowBand[] = [];
  for (const b of [...boxes].sort((p, q) => p.y - q.y)) {
    const r = rows.find((x) => Math.abs(x.top - b.y) < 0.5);
    if (r) r.bottom = Math.max(r.bottom, b.y + b.h);
    else rows.push({ top: b.y, bottom: b.y + b.h });
  }
  return rows;
}

/** The scroll box's height (screen px) when it is scrolled to `top`: the bottom of the last row that is whole within
 *  `room`, plus the pad; the whole room when not even one row fits. */
export function viewHeight(rows: RowBand[], k: number, top: number, room: number): number {
  let best = 0;
  for (const r of rows) {
    if (r.bottom * k <= top + 0.5) continue; // above the view
    const end = (r.bottom + PAD) * k - top;
    if (end <= room + 0.5) best = Math.max(best, end);
  }
  return Math.max(0, Math.min(room, best || room));
}

/** How many boxes lie wholly below a scroll box `h` px tall scrolled to `top`. */
export function belowCount(boxes: Placed[], k: number, top: number, h: number): number {
  return boxes.filter((b) => b.y * k >= top + h - 0.5).length;
}

/** r/batch04 entry 1: the scroll box's height. On Auto (`auto`: the session's row says so) the WHOLE room from the first
 *  draw, whatever fits whole (a group is far taller than a box; what does not fit is reached by the drawing's own
 *  scroll); on a map of his the released rule, `viewHeight`. */
export const drawingHeight = (auto: boolean, rows: RowBand[], k: number, top: number, room: number): number =>
  auto ? Math.max(0, room) : viewHeight(rows, k, top, room);

/** r/batch04 entry 1: the drawing's scrolled size (screen px). On Auto the box no longer shrinks under a press, so the
 *  scroll reaches far enough for any group's head to stand at the box's top (the slot's press, B26 B27); else the
 *  drawing's own height. */
export function scrollSize(auto: boolean, boxes: Placed[], k: number, h: number, viewH: number): number {
  const heads = auto ? boxes.filter((b) => b.id.startsWith("group:")).map((b) => b.y * k + viewH) : [];
  return Math.max(h * k, ...heads);
}

/** 3.6.0.5 B26 on Auto: the group box wholly below the view whose group (the AutoGroup of its `group.n`: the member
 *  states are the groups', never the box's) has a member working; the lowest n; null when none. `cut` (Session on Auto,
 *  whose view is the whole room, r/batch04 entry 1): a group not WHOLLY in view below it counts too -- its head in or
 *  below the view and its foot past the view's foot. */
export function workingBelow(boxes: PlacedDown[], groups: AutoGroup[], k: number, top: number, viewH: number, cut = false): PlacedDown | null {
  // 3.6.0.13 L4: working from the raw state (running, paused); a group whose members are all queued is not working
  const working = new Set(groups.filter((g) => g.members.some((m) => ["running", "paused"].includes(rawOf(m)))).map((g) => g.n));
  const out = (b: PlacedDown) => (cut ? b.y * k >= top - 0.5 && (b.y + b.h) * k > top + viewH + 0.5 : b.y * k >= top + viewH - 0.5);
  const below = boxes.filter((b) => b.group && working.has(b.group.n) && out(b));
  return below.sort((p, q) => p.group!.n - q.group!.n)[0] || null;
}

/** r/batch04 entry 1, Session's slot on Auto: the working group not wholly in view below (workingBelow with `cut`) and how
 *  many other boxes lie wholly below the view ("and {more} more below"); null when none. */
export function slotOf(boxes: PlacedDown[], groups: AutoGroup[], k: number, top: number, viewH: number): { box: PlacedDown; more: number } | null {
  const box = workingBelow(boxes, groups, k, top, viewH, true);
  return box ? { box, more: belowCount(boxes.filter((b) => b !== box), k, top, viewH) } : null;
}

/** A rect on screen (client px). */
export type Rect = { top: number; bottom: number; left: number; right: number };
/** A waiting member's rect, its group's n and its agent id. */
export type Seen = Rect & { n: number; aid: string };
export type SlotArrow = "down" | "up" | "under";

/** 3.6.0.13 L4: the group the slot names first -- one whose waiting member is out of sight (not wholly inside the view:
 *  partly in view counts) with the arrow of the edge that cuts it (its top above the view's top: up, else down), or
 *  wholly in view under the open card (`cover`): under; of several the lowest n; null when none. */
export function waitSlot(seen: Seen[], view: Rect, cover: Rect | null): { n: number; aid: string; arrow: SlotArrow } | null {
  const meets = (a: Rect, b: Rect) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  const at = seen.flatMap((x) => {
    const whole = x.top >= view.top - 0.5 && x.bottom <= view.bottom + 0.5;
    const arrow: SlotArrow | null = !whole ? (x.top < view.top - 0.5 ? "up" : "down") : cover && meets(x, cover) ? "under" : null;
    return arrow ? [{ n: x.n, aid: x.aid, arrow }] : [];
  });
  return at.sort((p, q) => p.n - q.n)[0] || null;
}

/** 3.6.0.13 L4: the group boxes wholly below a view `h` tall scrolled to `top`, group `n` (the one named) not counted. */
export const groupsBelow = (boxes: PlacedDown[], k: number, top: number, h: number, n: number): number =>
  boxes.filter((b) => b.group && b.group.n !== n && b.y * k >= top + h - 0.5).length;

/** R4: a press's steps in order -- with the card open, fold it first, then scroll; the under form only folds. */
export function slotPress(arrow: SlotArrow | "working", cardOpen: boolean): ("fold" | "scroll")[] {
  if (arrow === "under") return cardOpen ? ["fold"] : [];
  return cardOpen ? ["fold", "scroll"] : ["scroll"];
}

/** Where a press on a group's slot scrolls to (scroll px): its head at the top, or, when its waiting member's foot would
 *  still be out of a view `h` tall, that member's top. */
export const slotTop = (head: number, member: { top: number; bottom: number } | null, h: number): number =>
  member && member.bottom > head + h + 0.5 ? member.top : head;

/** The scrollTop that brings the next row's top to the scroll box's top (one row down), or null at the last row. */
export function nextTop(rows: RowBand[], k: number, top: number): number | null {
  let cur = 0;
  rows.forEach((r, i) => { if (r.top * k <= top + PAD * k + 1) cur = i; });
  const next = rows[cur + 1];
  return next ? next.top * k : null;
}

/** The first box he sees at `top` (its bottom below the scroll box's top) and how far below the top it starts. */
export function firstSeen(boxes: Placed[], k: number, top: number): { id: string; off: number } | null {
  const seen = boxes.filter((b) => (b.y + b.h) * k > top + 0.5).sort((p, q) => p.y - q.y)[0];
  return seen ? { id: seen.id, off: seen.y * k - top } : null;
}

/** The scrollTop that puts the box `seen` where it was, in the new drawing (null when it is gone). */
export function keepSeen(boxes: Placed[], k: number, seen: { id: string; off: number }): number | null {
  const b = boxes.find((x) => x.id === seen.id);
  return b ? Math.max(0, b.y * k - seen.off) : null;
}
