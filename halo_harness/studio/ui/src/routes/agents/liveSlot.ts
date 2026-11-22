// Agents -> 4 · Live on Auto (3.6.0.5 B26 B27, b/batch07): what the slot under the scroll box says for a scroll position,
// and what a stored "open this group" does at a draw of its session. Pure (tests/test_map_groups.py runs it in node):
// LiveDraw.tsx sets its state only when the slot's answer changes, at most once per animation frame.
import type { PlacedDown } from "../crew/map/layoutDown";
import type { AutoGroup } from "../crew/map/overlayGroups";
import { belowCount, workingBelow, type SlotArrow } from "../session/downFit";

/** The slot's answer: the group it names (its n) and how many boxes more wait below; null: it names none. 3.6.0.13 L4:
 *  `arrow` and `aid` when it names a group that waits on him (none on the working form). */
export type SlotAnswer = { n: number; more: number; arrow?: SlotArrow; aid?: string } | null;

/** The answer at scroll `top` of a view `h` tall at zoom `k` (null with no groups or no view). */
export function slotAnswer(boxes: PlacedDown[], groups: AutoGroup[] | undefined, k: number, top: number, h: number): SlotAnswer {
  const wb = groups && h > 0 ? workingBelow(boxes, groups, k, top, h) : null;
  const n = wb?.group?.n;
  return n == null ? null : { n, more: belowCount(boxes, k, top, h) - 1 };
}

/** The same words on the slot: the same group, form and count (or both none), and the same waiting member. */
export const sameAnswer = (a: SlotAnswer, b: SlotAnswer): boolean =>
  (!a || !b ? a === b : a.n === b.n && a.more === b.more && a.arrow === b.arrow && a.aid === b.aid);

/** A stored focus at a draw of session `sid`: "take" when its group is placed; "drop" at a full draw (every box placed
 *  and measured) that has not placed it, so no later draw jumps; else "wait" (another session's focus, or none: "none"). */
export function focusStep(focus: { sid: string; n: number } | null, sid: string, placed: boolean, full: boolean): "take" | "drop" | "wait" | "none" {
  if (!focus) return "none";
  if (focus.sid !== sid) return "wait";
  return placed ? "take" : full ? "drop" : "wait";
}
