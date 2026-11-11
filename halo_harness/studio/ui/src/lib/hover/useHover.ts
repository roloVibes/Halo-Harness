// What a box spreads on itself to get a hover card (lib/ui/HoverCard.tsx draws it): the pointer resting on the box for
// HOVER_DELAY shows it (a move restarts the wait), the keyboard focusing the box shows it after the same wait, leaving the
// box and the card hides it (a short grace lets the pointer cross to the card), and a pointer down on the box hides it
// until the pointer leaves (so it never sits over a click or a drag). On a small control inside the box (a button, a
// chip with its own `title`: `data-hover-skip`) the card goes, and comes back on the box's own surface. `titles` says
// whether the box should keep its plain `title` tooltips (the setting is off).
import { useRef, type FocusEvent, type PointerEvent, type ReactNode } from "react";
import { useHoverMode } from "./setting";
import { CARD_ID, hideHover, hideSoon, hoverId, keepHover, schedule, useShowing, type HoverKind } from "./store";

const CONTROLS = "button, a, input, select, textarea, [data-hover-skip]";

export type HoverProps = {
  onPointerEnter?: (e: PointerEvent<HTMLElement>) => void;
  onPointerMove?: (e: PointerEvent<HTMLElement>) => void;
  onPointerLeave?: (e: PointerEvent<HTMLElement>) => void;
  onPointerDown?: (e: PointerEvent<HTMLElement>) => void;
  onFocus?: (e: FocusEvent<HTMLElement>) => void;
  onBlur?: (e: FocusEvent<HTMLElement>) => void;
  "aria-describedby"?: string;
};

export type Hover = { props: HoverProps; titles: boolean; show: (el: HTMLElement | null) => void; hide: () => void };

/** Is the pointer on a small control of the box (not the box's own surface). */
function onControl(e: PointerEvent<HTMLElement>): boolean {
  const c = (e.target as Element | null)?.closest?.(CONTROLS);
  return !!c && c !== e.currentTarget && e.currentTarget.contains(c);
}

export function useHover(kind: HoverKind, key: string, render: () => ReactNode, enabled = true): Hover {
  const mode = useHoverMode();
  const live = enabled && mode === "on" && !!key;
  const id = hoverId(kind, key);
  const showing = useShowing(id);
  const spent = useRef(false);
  const draw = useRef(render);
  draw.current = render;
  const want = (el: HTMLElement, by: "pointer" | "focus") => schedule({ id, kind, key, el, by, render: () => draw.current() });
  const show = (el: HTMLElement | null) => live && el && want(el, "focus");
  const hide = () => hideHover(id);
  if (!live) return { props: {}, titles: mode === "off" || !enabled, show, hide };
  const props: HoverProps = {
    onPointerEnter: (e) => {
      spent.current = false;
      if (e.pointerType !== "touch" && !onControl(e)) want(e.currentTarget, "pointer");
    },
    onPointerMove: (e) => {
      if (e.pointerType === "touch" || spent.current) return;
      if (onControl(e)) return hideHover(id);
      keepHover();
      if (!showing) want(e.currentTarget, "pointer"); // a move restarts the rest
    },
    onPointerLeave: (e) => {
      spent.current = false;
      const to = e.relatedTarget;
      if (to instanceof Node && document.getElementById(CARD_ID)?.contains(to)) return;
      hideSoon(id);
    },
    onPointerDown: () => {
      spent.current = true;
      hideHover(id);
    },
    onFocus: (e) => {
      if (e.target === e.currentTarget && e.currentTarget.matches(":focus-visible")) want(e.currentTarget, "focus");
    },
    onBlur: (e) => {
      if (e.target === e.currentTarget) hideHover(id);
    },
    "aria-describedby": showing ? CARD_ID : undefined,
  };
  return { props, titles: false, show, hide };
}

/** Merge a box's own handler with the hover's (both run, the box's first). */
export function both<E>(a: ((e: E) => void) | undefined, b: ((e: E) => void) | undefined): ((e: E) => void) | undefined {
  if (!a) return b;
  if (!b) return a;
  return (e: E) => (a(e), b(e));
}
