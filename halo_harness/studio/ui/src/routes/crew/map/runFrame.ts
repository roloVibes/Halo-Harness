// The parts of a run's drawing that Session's Live drawer (session/MapDown.tsx, top to bottom) and Agents -> 4 · Live
// (agents/LiveDraw.tsx, left to right) share, imported by both, never copied (3.6.0.2 R10 R12 R18):
// - useStepCard: R18 a click on a box, a step row, a line or a label opens the step-in card for the agent the session's
//   rows name at that moment (stepInTarget.ts); the same thing again closes it; another box's replaces it;
// - useHeld: R12 under the pointer (or with a card open) the last laid-out geometry stays, once every box is measured; a
//   different map (or width) is drawn at once; the change is drawn when the pointer leaves;
// - useMeasure: R10 each box as tall as its words, measured once drawn (as MapCanvas.tsx measures).
import { useCallback, useLayoutEffect, useRef, useState, type Dispatch, type RefObject, type SetStateAction } from "react";
import { useStore } from "../../../lib/store";
import { cover, type Where } from "./cover";
import type { Lit } from "./LitMini";
import type { LinePick } from "./RunLine";
import { stepIn, type Hit, type Target } from "./stepInTarget";

/** `open`: the drawing's sheet is placed (it set `cover`): the slot's answer is worked out again then. */
export function useStepCard(L: Lit, where: Where) {
  const [card, setCard] = useState<Target | null>(null);
  const rowsNow = useRef(L);
  rowsNow.current = L;
  const pick = useCallback((h: Hit) => setCard((c) => { // from the rows at the click
    const t = stepIn(h, rowsNow.current.agents, rowsNow.current.ov, rowsNow.current.groups);
    return c && c.id === t.id ? null : t;
  }), []);
  const pickLine: LinePick = useCallback((l, text) => pick({ kind: "line", from: l.from, to: l.to, text, off: !!l.off }), [pick]);
  const closeCard = useCallback(() => setCard(null), []);
  const open = useStore(cover, (c) => !!c[where]);
  return { card, setCard, pick, pickLine, closeCard, open };
}

/** The box a card is open on carries the selected mark (`data-selected`): its own card, or a block's head or step's;
 *  3.6.0.5 B13: a group's box (`members` given) for its own card (`group:{n}`, its id) and for a card on one of its members. */
export const selected = (card: Target | null, id: string, workflow?: string, members?: string[]): boolean =>
  !!card && (card.id === `box:${id}` || (!!workflow && (card.id === `head:${workflow}` || card.id.startsWith(`step:${workflow}:`)))
    || (!!members && (card.id === id || (card.id.startsWith("member:") && members.includes(card.id.slice(7))))));

/** useHeld's `ready`: every box measured, and at least one box. A drawing with no box yet (its rows or its map still
 *  coming, as when Watch it in Live lands on a run under the pointer) is never held: there is nothing in it to move. */
export const drawnAll = (boxes: { id: string }[], heights: Record<string, number>): boolean =>
  boxes.length > 0 && boxes.every((b) => heights[b.id] != null);

/** The geometry to draw: `fresh` unless held, measured, and still the same drawing (`key`: the map, and the width laid out). */
export function useHeld<G>(held: boolean, key: string, fresh: G, ready: boolean): G {
  const kept = useRef<{ key: string; g: G; ready: boolean } | null>(null);
  const was = kept.current;
  if (!held || !was || !was.ready || was.key !== key) kept.current = { key, g: fresh, ready };
  return kept.current!.g;
}

/** Measures each `[data-box]` under `world` after every draw and grows `heights` when a box's words need it; `shownOnly`:
 *  never while the view is hidden (a hidden view's boxes measure as their padding alone). */
export function useMeasure(world: RefObject<HTMLElement | null>, heights: Record<string, number>,
                           setHeights: Dispatch<SetStateAction<Record<string, number>>>, shownOnly = false): void {
  useLayoutEffect(() => {
    if (shownOnly && !world.current?.offsetParent) return;
    const got: Record<string, number> = {}, held: string[] = [];
    world.current?.querySelectorAll<HTMLElement>("[data-box]").forEach((el) => {
      got[el.dataset.box!] = (el.querySelector<HTMLElement>(".mp-inner")?.offsetHeight || 0) + (Number(el.dataset.pad) || 20); // its words, padding and border (a group's: data-pad)
      if (el.dataset.hold != null) held.push(el.dataset.box!);
    });
    const next = nextHeights(heights, got, held);
    if (next) setHeights((x) => ({ ...x, ...next }));
  });
}

/** The heights after a measure, or null when none changed by more than 1 px; k/batch02 entry 1: a box in `held` (main on
 *  Auto, `data-hold`) never measures shorter than it was -- when its words need more room it grows and holds that. */
export function nextHeights(heights: Record<string, number>, got: Record<string, number>, held: string[]): Record<string, number> | null {
  const next: Record<string, number> = {};
  for (const [id, h] of Object.entries(got)) next[id] = held.includes(id) ? Math.max(h, heights[id] || 0) : h;
  return Object.entries(next).some(([id, h]) => Math.abs((heights[id] || 0) - h) > 1) ? next : null;
}
