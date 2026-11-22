// 3.6.0.13 L6: the ring drawn, on Agents -> Live (agents/LiveDraw.tsx) and Session's map (session/MapDown.tsx). After each
// draw it reads the boxes on screen (each member `[data-member]` with its raw state from the groups, each group
// `[data-box^="group:"]` with the HELD geometry's drawn members), the box under the pointer and the open card (cover.ts),
// and asks rings.ts which ring against the last draw's boxes. Each ring sets `data-ring` on its box (live-now.css draws it
// as ::after, once) and bumps a kept counter `data-rang` (the browser tests read it after the fact); ONE animationend
// listener { once: true } takes `data-ring` off (re-added when another animation ends first, as LiveDraw.tsx's pulse):
// no timer, no animation frame. While the drawing is not shown the last boxes are cleared, so coming back rings nothing.
// Under reduced motion nothing is set.
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
  el.removeAttribute("data-ring");
  void el.offsetWidth; // a ring set again restarts its animation
  const end = (e: AnimationEvent) => {
    if (e.target !== el || !RING_ANIMATIONS.includes(e.animationName)) return void el.addEventListener("animationend", end, { once: true });
    el.removeAttribute("data-ring");
    off.delete(el);
  };
  el.addEventListener("animationend", end, { once: true });
  el.setAttribute("data-ring", kind);
  el.setAttribute("data-rang", String((Number(el.dataset.rang) || 0) + 1));
  off.set(el, () => (el.removeEventListener("animationend", end), el.removeAttribute("data-ring")));
}

/** `geometry`: the drawing as drawn (held or fresh); `now`: the drawing's clock in seconds; `shown`: the view on screen. */
export function useRings(where: Where, world: RefObject<HTMLElement | null>, scroll: RefObject<HTMLElement | null>,
                         geometry: { boxes: PlacedDown[] }, groups: AutoGroup[] | undefined, now: number, shown: boolean): void {
  const prev = useRef<RingBox[]>([]), last = useRef<Record<string, number>>({});
  useLayoutEffect(() => {
    const w = world.current, el = scroll.current;
    if (!shown || !w || !el) return void (prev.current = []);
    const next = boxesOf(w, geometry.boxes, groups), ms = now * 1000;
    const rings = ringEvents(prev.current, next, { ...viewOf(el), pointer: pointerOf(w), now: ms }, coverOf(where), last.current);
    prev.current = next;
    if (!rings.length || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    for (const r of rings) {
      const box = r.id.startsWith("group:") ? w.querySelector<HTMLElement>(`[data-box="${CSS.escape(r.id)}"]`)
        : w.querySelector<HTMLElement>(`[data-member="${CSS.escape(r.id)}"]`);
      if (box) (last.current[r.id] = ms, ring(box, r.kind));
    }
  }, [geometry, groups, shown]); // eslint-disable-line react-hooks/exhaustive-deps
}
