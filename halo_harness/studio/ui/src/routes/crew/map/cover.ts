// 3.6.0.13 L4 with R4: what the open step-in card (StepIn.tsx, `map-step-in`: "the open box" of the design; OP1's sheet is
// not in this release) covers on each drawing, and the slot's waiting form. `cover`: each drawing's open card (null when
// closed), set in a layout effect on its card before the slot's answer is worked out; its rect is read when the answer
// is (rectNow), so a resize that moves the card never leaves a stale one. `waitingSeen`: every waiting member's place
// (placeOf: a member past the eight drawn stands at its group's "+n more" row); `waitAnswer`: the group that waits on him
// the slot names first (downFit.ts waitSlot), else null. `useSlotGo`: a press with the card open folds it first (and
// clears `cover`); the scroll it asked for is made in a layout effect once the card is closed, never while it is open;
// the under form only folds.
import { useLayoutEffect, useRef, type RefObject } from "react";
import { createStore } from "../../../lib/store";
import type { SlotAnswer } from "../../agents/liveSlot";
import { groupsBelow, placeOf, rectNow, slotPress, slotTop, waitSlot, type Rect, type Seen, type SlotArrow } from "../../session/downFit";
import { rawOf } from "./groupWords";
import type { PlacedDown } from "./layoutDown";
import type { AutoGroup } from "./overlayGroups";

export type Where = "session" | "live";
export const cover = createStore<Record<Where, Element | null>>({ session: null, live: null });
export const setCover = (where: Where, el: Element | null): void => cover.update(() => ({ [where]: el }));
export const coverOf = (where: Where): Rect | null => rectNow(cover.get()[where]);

/** The scroll box's inner rect on screen (its view). */
function viewOf(el: HTMLElement): Rect {
  const r = el.getBoundingClientRect(), top = r.top + el.clientTop, left = r.left + el.clientLeft;
  return { top, bottom: top + el.clientHeight, left, right: left + el.clientWidth };
}
const memberEl = (world: HTMLElement | null, aid: string) => world?.querySelector<HTMLElement>(`[data-member="${CSS.escape(aid)}"]`) || null;

/** Every member whose raw state is `waiting`, its group's n and its place on screen (a member not on the page is left out). */
export function waitingSeen(world: HTMLElement | null, groups: AutoGroup[]): Seen[] {
  return groups.flatMap((g) => g.members.filter((m) => rawOf(m) === "waiting").flatMap((m) => {
    const r = placeOf(memberEl(world, m.aid));
    return r ? [{ ...r, n: g.n, aid: m.aid }] : [];
  }));
}

/** The slot's waiting answer on drawing `where` (scroll box `el` scrolled to `top`, `h` tall), with the other groups below. */
export function waitAnswer(where: Where, world: HTMLElement | null, el: HTMLElement, groups: AutoGroup[], boxes: PlacedDown[], k: number,
  top: number, h: number): SlotAnswer {
  const w = waitSlot(waitingSeen(world, groups), viewOf(el), coverOf(where));
  return w && { ...w, more: groupsBelow(boxes, k, top, h, w.n) };
}

/** Where a press on answer `a` scrolls (scroll px): the group's head at the top, or its waiting member's top when the
 *  member's foot would still be out of view (downFit.ts slotTop). */
export function slotAim(world: HTMLElement | null, el: HTMLElement, a: NonNullable<SlotAnswer>, head: number, h: number): number {
  const r = a.aid ? placeOf(memberEl(world, a.aid)) : null;
  if (!r) return head;
  const v = viewOf(el);
  return slotTop(head, { top: el.scrollTop + r.top - v.top, bottom: el.scrollTop + r.bottom - v.top }, h);
}

/** R4: sets `cover` from the open card, and returns the slot's press: `arrow` (undefined: the working form), `t` its target. */
export function useSlotGo(where: Where, root: RefObject<HTMLElement | null>, card: unknown, closeCard: () => void, scrollTo: (t: number) => void) {
  const after = useRef<number | null>(null);
  useLayoutEffect(() => {
    setCover(where, card ? root.current?.querySelector("[data-testid=map-step-in]") || null : null);
  }, [card]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { // the scroll a press asked for while the card was open: made once it is closed
    if (card || after.current == null) return;
    const t = after.current;
    after.current = null;
    scrollTo(t);
  }, [card]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => () => setCover(where, null), []); // eslint-disable-line react-hooks/exhaustive-deps
  return (arrow: SlotArrow | undefined, t: number | null) => {
    for (const step of slotPress(arrow || "working", !!card)) {
      if (step === "fold") (setCover(where, null), closeCard());
      else if (t != null && card) after.current = t;
      else if (t != null) scrollTo(t);
    }
  };
}
