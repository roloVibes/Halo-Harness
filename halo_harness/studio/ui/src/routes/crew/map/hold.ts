// Nothing moves under the pointer (3.6.0.2 R12), shared by Session's Live drawer and Agents' Live view: while the pointer
// is over the drawing's root (the drawing, its head, its "↓" slot, its card) or a card is open, the drawing keeps its last
// laid-out geometry; the change that moves a box (a box, a row, a block arriving) is drawn when the pointer leaves. On
// touch a lifted finger (`pointerup`) or 2 s with no move counts as leaving. Free of Session imports (P4 uses it as is).
import { useEffect, useRef, useState, type RefObject } from "react";

export const TOUCH_STILL_MS = 2000;

export function useHold(root: RefObject<HTMLElement | null>, cardOpen = false): { held: boolean } {
  const [inside, setInside] = useState(false);
  const bound = useRef<{ el: HTMLElement; off: () => void } | null>(null);
  useEffect(() => { // bound again whenever the root is a new element (a drawing that draws its root once its data is in)
    const el = root.current;
    if (bound.current?.el === el) return;
    bound.current?.off();
    bound.current = el ? { el, off: watch(el, setInside) } : null;
  });
  useEffect(() => () => bound.current?.off(), []);
  return { held: inside || cardOpen };
}

function watch(el: HTMLElement, set: (on: boolean) => void): () => void {
  let still = 0;
  const leave = () => (window.clearTimeout(still), set(false));
  const touched = () => (window.clearTimeout(still), (still = window.setTimeout(leave, TOUCH_STILL_MS)));
  const over = (e: PointerEvent) => (set(true), e.pointerType === "touch" ? touched() : undefined);
  const up = (e: PointerEvent) => (e.pointerType === "touch" ? leave() : undefined);
  el.addEventListener("pointerenter", over);
  el.addEventListener("pointermove", over);
  el.addEventListener("pointerleave", leave);
  el.addEventListener("pointerup", up);
  el.addEventListener("pointercancel", leave);
  return () => {
    window.clearTimeout(still);
    el.removeEventListener("pointerenter", over);
    el.removeEventListener("pointermove", over);
    el.removeEventListener("pointerleave", leave);
    el.removeEventListener("pointerup", up);
    el.removeEventListener("pointercancel", leave);
  };
}
