// Zoom and pan, the same on every drawing in Studio (3.4.1.3; the owner, 2026-11-12, at Session's Map drawn too small to
// read: "a ctrl+mouse up and down would be nice to zoom in via a mouse. It should work for Mac and windows style
// mouse's"). One module, used by Agents -> Live (and a replay on its scrubber), Session's Map, Agents -> Cast and the
// design pack's artboards:
// - Ctrl + wheel (Windows, Linux) or Cmd + wheel (macOS) zooms around the pointer; a trackpad pinch arrives as a wheel
//   event with ctrlKey and small pixel deltas and zooms smoothly; a wheel notch (lines, or a big pixel delta) is one
//   step. Only over the canvas is the browser's own page zoom held back (preventDefault there and only there).
// - A plain wheel scrolls as it always did (two fingers on a trackpad pan both ways); Shift + wheel pans sideways for
//   a mouse with one wheel. deltaMode is read: pixels, lines (16 px) or pages.
// - Keys on the focused canvas: + and - zoom, 0 fits. Drag the empty background to pan; double-click it to fit.
// - The zoom is kept per canvas for the visit (`id`), never across a reload.
import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";

export const ZOOM_MIN = 0.12;
export const ZOOM_MAX = 2.5;
/** Below this the boxes' text is too small to read (12 px text at 0.75 is 9 px). */
export const READABLE = 0.75;
export const NAV_HELP = "Ctrl + wheel (Cmd on a Mac) or pinch to zoom, drag to pan, double-click to fit.";

export const clampZoom = (z: number, min = ZOOM_MIN, max = ZOOM_MAX) => Math.max(min, Math.min(max, z));

/** How much one wheel event zooms: a pinch or a precision touchpad (small pixel deltas) smoothly, a notch one step. */
export function wheelFactor(e: { deltaY: number; deltaMode: number }, pageH = 800): number {
  const px = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * pageH : e.deltaY;
  if (!px) return 1;
  if (e.deltaMode === 0 && Math.abs(px) < 50) return Math.exp(-px * 0.01);
  return px < 0 ? 1.1 : 1 / 1.1;
}

const kept = new Map<string, number>();
/** The zoom this canvas had earlier in this visit (`undefined`: none yet). */
export const recallZoom = (id: string): number | undefined => kept.get(id);
export const keepZoom = (id: string, z: number): void => void kept.set(id, z);

/** A zoom that keeps the drawing's point under (px, py) -- the pointer, else the middle of the view -- where it was. */
export function useZoomPoint(scroll: RefObject<HTMLElement | null>, zoom: number, setZoom: (z: number) => void) {
  const pending = useRef<{ cx: number; cy: number; px: number; py: number } | null>(null);
  const zref = useRef(zoom);
  zref.current = zoom;
  useLayoutEffect(() => {
    const p = pending.current, el = scroll.current;
    if (!p || !el) return;
    pending.current = null;
    el.scrollLeft = p.cx * zoom - p.px;
    el.scrollTop = p.cy * zoom - p.py;
  }, [zoom]);
  return (z: number, px?: number, py?: number) => {
    const el = scroll.current;
    if (el) {
      const ax = px ?? el.clientWidth / 2, ay = py ?? el.clientHeight / 2;
      pending.current = { cx: (el.scrollLeft + ax) / zref.current, cy: (el.scrollTop + ay) / zref.current, px: ax, py: ay };
    }
    setZoom(z);
  };
}

export type Nav = {
  zoom: number;
  /** Zoom to z with the point (px, py) of the view held still. */
  zoomAt: (z: number, px?: number, py?: number) => void;
  fit: () => void;
  min?: number;
  max?: number;
  /** The empty background (where a drag pans and a double-click fits); default: the scroller and its world layers. */
  background?: string;
  /** The canvas's own name for the visit's memory of its zoom. */
  id?: string;
};

const TYPING = "input, textarea, select, [contenteditable]";
/** The empty background of a drawing: the scroller's world layers and the inside of a box that holds others (a tier,
 *  a group, a block) -- the element itself, never its head, its cards or its buttons. */
const BACKGROUND = ".rc-world, .rc-inner, .da-world, .cz-world, .rc-tier, [data-testid=\"roles-live-group\"], [data-testid=\"live-group\"], [data-testid=\"live-block\"]";

/** Wire the wheel, the keys, the background drag and the double-click on the scroller `scroll` (bound again whenever
 *  the scroller is a new element: a canvas that draws its scroller only once its data is in). */
export function useCanvasNav(scroll: RefObject<HTMLElement | null>, nav: Nav): void {
  const cur = useRef(nav);
  cur.current = nav;
  const bound = useRef<{ el: HTMLElement; off: () => void } | null>(null);
  useEffect(() => {
    if (nav.id) keepZoom(nav.id, nav.zoom);
  }, [nav.id, nav.zoom]);
  useEffect(() => {
    const el = scroll.current;
    if (bound.current?.el === el) return;
    bound.current?.off();
    bound.current = el ? { el, off: attach(el, cur) } : null;
  });
  useEffect(() => () => bound.current?.off(), []);
}

function attach(el: HTMLElement, cur: { current: Nav }): () => void {
  const bg = (t: EventTarget | null) => t === el || !!(t as Element | null)?.matches?.(cur.current.background || BACKGROUND);
  const onWheel = (e: WheelEvent) => {
    const n = cur.current;
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault(); // the page's own zoom stays as it is while the pointer is over the drawing
      const r = el.getBoundingClientRect();
      const z = clampZoom(n.zoom * wheelFactor(e, el.clientHeight), n.min, n.max);
      if (Math.abs(z - n.zoom) > 1e-4) n.zoomAt(z, e.clientX - r.left, e.clientY - r.top);
    } else if (e.shiftKey && !e.deltaX && e.deltaY) {
      e.preventDefault();
      el.scrollLeft += e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
    }
  };
  const onKey = (e: KeyboardEvent) => {
    const n = cur.current;
    if (e.ctrlKey || e.metaKey || e.altKey || e.defaultPrevented || (e.target as Element | null)?.closest?.(TYPING)) return;
    if (e.key === "+" || e.key === "=") n.zoomAt(clampZoom(n.zoom * 1.2, n.min, n.max));
    else if (e.key === "-" || e.key === "_") n.zoomAt(clampZoom(n.zoom / 1.2, n.min, n.max));
    else if (e.key === "0") n.fit();
    else return;
    e.preventDefault();
  };
  let pan: { x: number; y: number; sl: number; st: number; moved: boolean } | null = null;
  const onMove = (e: PointerEvent) => {
    if (!pan) return;
    const dx = e.clientX - pan.x, dy = e.clientY - pan.y;
    if (!pan.moved && Math.hypot(dx, dy) < 4) return;
    pan.moved = true;
    el.dataset.panning = "1";
    el.scrollLeft = pan.sl - dx;
    el.scrollTop = pan.st - dy;
  };
  const onUp = () => {
    const moved = pan?.moved;
    pan = null;
    delete el.dataset.panning;
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    if (moved) el.addEventListener("click", (c) => c.stopPropagation(), { capture: true, once: true }); // a pan is not a click
  };
  const onDown = (e: PointerEvent) => {
    if (e.button !== 0 || !bg(e.target)) return;
    pan = { x: e.clientX, y: e.clientY, sl: el.scrollLeft, st: el.scrollTop, moved: false };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };
  const onDbl = (e: MouseEvent) => {
    if (bg(e.target)) (e.preventDefault(), cur.current.fit());
  };
  el.addEventListener("wheel", onWheel, { passive: false });
  el.addEventListener("keydown", onKey);
  el.addEventListener("pointerdown", onDown);
  el.addEventListener("dblclick", onDbl);
  return () => {
    el.removeEventListener("wheel", onWheel);
    el.removeEventListener("keydown", onKey);
    el.removeEventListener("pointerdown", onDown);
    el.removeEventListener("dblclick", onDbl);
    onUp();
  };
}
