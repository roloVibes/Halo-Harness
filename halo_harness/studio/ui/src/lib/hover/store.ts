// The one hover card of the page (3.3.16.1, the owner: "hovering over gives a solid summary, if we click one we get that
// other panel with all the detail"): which box it describes, the element it sits beside, how it came (the pointer rested
// on the box, or the keyboard focused it) and what it says (a render function, so its content reads the stores live).
// One card at a time for the whole page: showing one replaces the last. The timers live here too -- the rest delay
// (HOVER_DELAY), and the short grace that lets the pointer cross the gap from a box to its card -- and the page-wide
// reasons it goes: Esc, Enter, a scroll or a wheel, a pointer down outside it, a drag, a resize (installHoverListeners).
import type { ReactNode } from "react";
import { createStore, useStore } from "../store";

export type HoverKind = "cast" | "agent" | "session" | "machine" | "lane" | "part" | "square" | "group" | "when"; // when: 3.3.16.3, a block's line
export type Shown = { id: string; kind: HoverKind; key: string; el: HTMLElement; by: "pointer" | "focus"; render: () => ReactNode };

export const HOVER_DELAY = 350;
export const GRACE_MS = 140;
export const CARD_ID = "halo-hover-card";

export const hover = createStore<{ shown: Shown | null }>({ shown: null });

let timer = 0;
let pending = "";
let graceTimer = 0;

/** The card's id for a box: its kind and its key (a session and its main agent share a fleet key). */
export const hoverId = (kind: HoverKind, key: string): string => `${kind}:${key}`;

export const isPending = (id: string): boolean => pending === id;

/** Show `s` after `ms` (the rest delay); a later call replaces it. */
export function schedule(s: Shown, ms = HOVER_DELAY): void {
  window.clearTimeout(timer);
  if (hover.get().shown?.id === s.id) window.clearTimeout(graceTimer); // back on the box whose card shows: it stays
  pending = s.id;
  timer = window.setTimeout(() => {
    pending = "";
    if (s.el.isConnected) hover.update(() => ({ shown: s }));
  }, ms);
}

/** Forget a pending show (all, or only box `id`'s). */
export function cancelPending(id = ""): void {
  if (id && pending !== id) return;
  window.clearTimeout(timer);
  pending = "";
}

/** Hide at once (the card of box `id` only, or whichever shows). */
export function hideHover(id = ""): void {
  cancelPending(id);
  window.clearTimeout(graceTimer);
  const cur = hover.get().shown;
  if (cur && (!id || cur.id === id)) hover.update(() => ({ shown: null }));
}

/** Hide after the grace (the pointer may be crossing to the card). */
export function hideSoon(id: string): void {
  cancelPending(id);
  window.clearTimeout(graceTimer);
  graceTimer = window.setTimeout(() => hideHover(id), GRACE_MS);
}

export const keepHover = (): void => window.clearTimeout(graceTimer);

/** Is box `id`'s card the one showing (its aria-describedby). */
export const useShowing = (id: string): boolean => useStore(hover, (s) => s.shown?.id === id);

let installed = false;

/** Once per page: the reasons a card goes that are not its box's own (Esc, Enter, a scroll, a click elsewhere, a drag). */
export function installHoverListeners(): void {
  if (installed) return;
  installed = true;
  const card = () => document.getElementById(CARD_ID);
  const inCard = (t: EventTarget | null) => !!(t instanceof Node && card()?.contains(t));
  window.addEventListener("keydown", (e) => (e.key === "Escape" || e.key === "Enter" || e.key === " ") && hideHover(), true);
  window.addEventListener("scroll", (e) => !inCard(e.target) && hideHover(), true);
  window.addEventListener("wheel", (e) => !inCard(e.target) && hideHover(), { capture: true, passive: true });
  window.addEventListener("pointerdown", (e) => !inCard(e.target) && hideHover(), true);
  window.addEventListener("dragstart", () => hideHover(), true);
  window.addEventListener("resize", () => hideHover());
}
