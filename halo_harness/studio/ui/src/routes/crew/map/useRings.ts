// 3.6.0.13 L6: the ring drawn, on Agents -> Live (agents/LiveDraw.tsx) and Session's map (session/MapDown.tsx). After each
// draw it reads the boxes on screen (each member `[data-member]` with its raw state from the groups, each group
// `[data-box^="group:"]` with the HELD geometry's drawn members), the box under the pointer and the open card (cover.ts),
// and asks rings.ts which ring against the last draw's boxes. Each ring sets `data-ring` on its box (live-now.css draws it
// as ::after, once) and bumps a kept counter `data-rang` (the browser tests read it after the fact); ONE animationend
// listener { once: true } takes `data-ring` off (re-added when another animation ends first, as LiveDraw.tsx's pulse),
// and so does the ring's animationcancel (its box hidden while it plays: a ring cut off never plays again): no timer,
// no animation frame. While the drawing is not shown the last boxes are cleared and every ring is taken off, so coming
// back rings nothing. The first draw rings nothing; once the session was drawn (its boxes, or main alone while it has
// no helper yet), a new group rings HAND: the first hand-out of a session too. A draw whose boxes are gone (a frame
// without the session's agents) makes the next draw a first draw again. Under reduced motion nothing is set.
import { useLayoutEffect, useRef, type RefObject } from "react";
import { coverOf, type Where } from "./cover";
import { rawOf } from "./groupWords";
import type { PlacedDown } from "./layoutDown";
import type { AutoGroup } from "./overlayGroups";
import { ringEvents, type RingBox, type RingKind } from "./rings";

export const RING_ANIMATIONS = ["mp-ring-shake", "mp-ring-fade"];
const off = new WeakMap<HTMLElement, () => void>();

/** A box's rect on screen; a box not laid out (a hidden member) is never in view. */
function rectOf(el: HTMLElement) {
  const r = el.getBoundingClientRect();
  return r.width || r.height ? { top: r.top, bottom: r.bottom, left: r.left, right: r.right }
    : { top: -Infinity, bottom: -Infinity, left: -Infinity, right: -Infinity };
}

function boxesOf(world: HTMLElement, boxes: PlacedDown[], groups: AutoGroup[] | undefined): RingBox[] {
  const raw = new Map((groups || []).flatMap((g) => g.members.map((m) => [m.aid, rawOf(m)] as const)));
  const drawn = new Map(boxes.filter((b) => b.group).map((b) => [b.id, b.group!.members]));
  const out: RingBox[] = [];
  world.querySelectorAll<HTMLElement>("[data-member]").forEach((el) => {
    const id = el.dataset.member!;
    out.push({ id, kind: "member", raw: raw.get(id) || el.dataset.raw, ...rectOf(el) });
  });
  world.querySelectorAll<HTMLElement>('[data-box^="group:"]').forEach((el) => {
    const id = el.dataset.box!;
    out.push({ id, kind: "group", members: drawn.get(id) || [], ...rectOf(el) });
  });
  return out;
}

/** The box under the pointer: the member it is on, else the group. */
function pointerOf(world: HTMLElement): string | null {
  const m = world.querySelector<HTMLElement>("[data-member]:hover");
  if (m) return m.dataset.member!;
  return world.querySelector<HTMLElement>('[data-box^="group:"]:hover')?.dataset.box || null;
}

function viewOf(el: HTMLElement) {
  const r = el.getBoundingClientRect(), top = r.top + el.clientTop, left = r.left + el.clientLeft;
  return { top, bottom: top + el.clientHeight, left, right: left + el.clientWidth };
}

/** Rings box `el` once: `data-ring` until its ring's animation ends (one listener), `data-rang` counts every ring. */
export function ring(el: HTMLElement, kind: RingKind): void {
  off.get(el)?.();
  void el.offsetWidth; // a ring set again restarts its animation
  const stop = () => {
    el.removeEventListener("animationend", end);
    el.removeEventListener("animationcancel", end);
    el.removeAttribute("data-ring");
    off.delete(el);
  };
  const end = (e: AnimationEvent) => {
    if (e.target !== el || !RING_ANIMATIONS.includes(e.animationName)) return void el.addEventListener(e.type as "animationend", end, { once: true });
    stop();
  };
  el.addEventListener("animationend", end, { once: true });
  el.addEventListener("animationcancel", end, { once: true }); // cut off (its box hidden while it plays): over, never played again
  el.setAttribute("data-ring", kind);
  el.setAttribute("data-rang", String((Number(el.dataset.rang) || 0) + 1));
  off.set(el, stop);
}

/** `geometry`: the drawing as drawn (held or fresh); `now`: the drawing's clock in seconds; `shown`: the view on screen. */
export function useRings(where: Where, world: RefObject<HTMLElement | null>, scroll: RefObject<HTMLElement | null>,
                         geometry: { boxes: PlacedDown[] }, groups: AutoGroup[] | undefined, now: number, shown: boolean): void {
  const prev = useRef<RingBox[]>([]), last = useRef<Record<string, number>>({}), seen = useRef(false), had = useRef(false);
  useLayoutEffect(() => {
    const w = world.current, el = scroll.current;
    if (!shown || !w || !el || !groups) {
      w?.querySelectorAll<HTMLElement>("[data-ring]").forEach((b) => (off.get(b)?.(), b.removeAttribute("data-ring")));
      return void (prev.current = [], seen.current = false, had.current = false);
    }
    const next = boxesOf(w, geometry.boxes, groups), ms = now * 1000;
    const rings = ringEvents(prev.current, next, { ...viewOf(el), pointer: pointerOf(w), now: ms }, coverOf(where), last.current, !seen.current);
    prev.current = next;
    // drawn once: its boxes, or main alone while the session has no helper yet (a draw that has helpers and no box yet
    // is not one); boxes that were drawn and are gone for a draw are a gap in the data, never "main alone"
    if (next.length) had.current = seen.current = true;
    else if (had.current) seen.current = false;
    else seen.current = seen.current || (!groups.length && !!w.querySelector("[data-box=main]"));
    if (!rings.length || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    for (const r of rings) {
      const box = r.id.startsWith("group:") ? w.querySelector<HTMLElement>(`[data-box="${CSS.escape(r.id)}"]`)
        : w.querySelector<HTMLElement>(`[data-member="${CSS.escape(r.id)}"]`);
      if (box) (last.current[r.id] = ms, ring(box, r.kind));
    }
  }, [geometry, groups, shown]); // eslint-disable-line react-hooks/exhaustive-deps
}
