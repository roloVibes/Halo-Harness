// The step-in sheet's place and its coming and going (3.6.0.14 OP1, rules O1-2 and O1-3); StepIn.tsx keeps its layout.
// - At open (once its words are read, `ready`: O1-6's GET answered or 1 s passed) it is drawn at its width, hidden
//   (`data-place="measure"`, no test id), and measured; then placed ONCE, never re-placed: Agents -> Live by
//   sheetPlace.ts agentsPlace (`data-place="sheet"`), Session's drawer by drawerPlace (`data-place="drawer"`), with
//   `data-side`. Every rect is downFit.ts's (rectNow, placeOf: a hidden member stands at its "+n more" row) taken to
//   the frame's px (the sheet's offset parent, `.ag-run` / `.mp-down`).
// - Agents unfolds it from its box's rectangle (`--sheet-from`, map-down.css) and folds it back; the drawer opens and
//   closes at once. It is pressable (`map-step-in`, `data-open`, not inert) once the unfold ended -- on `transitionend`,
//   `transitioncancel`, reduced motion, a 0 s transition, no anchor, or at the latest 400 ms (a runner that reduces motion
//   may never fire `transitionend`).
// - It sets `cover` (cover.ts) once placed and clears it when its fold starts or it goes.
// - What folds it is sheetPlace.ts sheetClose: Escape, x, a pointer-down outside (a box of this drawing is the click's
//   pick; the slot's own press folds it first, R4), a wheel over the drawing, a zoom since the open. A view that hid
//   (Studio keeps a visited section mounted: leaving it, by a click or a key, fires no unmount) closes it at once, seen
//   by a ResizeObserver on the sheet (0 x 0 once hidden). No listener, no observer and no timer outlives it.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { placeOf, rectNow, type Rect } from "../../session/downFit";
import { setCover, type Where } from "./cover";
import { agentsPlace, anchorSel, drawerPlace, fromInset, insetOf, sheetClose, type Place, type SheetEvent } from "./sheetPlace";
import type { Target } from "./stepInTarget";

const LAST_MS = 400;
const PICK = "[data-box], [data-member], .mp-label, .mp-hit";
const SLOT = "[data-testid=live-more-below], [data-testid=map-more-below]";
type Geo = { frame: HTMLElement; width: number; anchor: Rect | null; view: Rect; size: { width: number; height: number }; zoom: string | null };

const less = (r: Rect, x: number, y: number): Rect => ({ top: r.top - y, bottom: r.bottom - y, left: r.left - x, right: r.right - x });
const zoomOf = (frame: HTMLElement): string | null => frame.querySelector("[data-pan] [data-zoom]")?.getAttribute("data-zoom") ?? null;
const hidden = (el: HTMLElement): boolean => !el.isConnected || !el.getClientRects().length;
/** No motion to wait for: reduced motion, or a transition of 0 s. */
const still = (el: HTMLElement): boolean => matchMedia("(prefers-reduced-motion: reduce)").matches
  || getComputedStyle(el).transitionDuration.split(",").every((d) => !parseFloat(d));

function geoOf(el: HTMLElement, where: Where, id: string): Geo | null {
  const frame = el.offsetParent as HTMLElement | null, f = frame && rectNow(frame);
  if (!frame || !f) return null; // its view is hidden: placed once it shows
  const x = f.left + frame.clientLeft, y = f.top + frame.clientTop, size = { width: frame.clientWidth, height: frame.clientHeight };
  const pan = rectNow(frame.querySelector("[data-pan]")), sel = anchorSel(id, CSS.escape), a = sel ? placeOf(frame.querySelector(sel)) : null;
  const view = pan ? less(pan, x, y) : { top: 0, left: 0, right: size.width, bottom: size.height };
  const anchor = a && less(a, x, y);
  const width = where === "live" ? agentsPlace(anchor, view, 0).width : drawerPlace(anchor, view, size, 0).width;
  return { frame, width, anchor, view, size, zoom: zoomOf(frame) };
}

/** Calls `done` once, at the end of `el`'s unfold or fold or at the latest LAST_MS; returns its undo. */
function onEnd(el: HTMLElement, done: () => void): () => void {
  const end = (e: TransitionEvent) => e.target === el && (off(), done());
  const timer = setTimeout(() => (off(), done()), LAST_MS);
  const off = () => (el.removeEventListener("transitionend", end), el.removeEventListener("transitioncancel", end), clearTimeout(timer));
  el.addEventListener("transitionend", end);
  el.addEventListener("transitioncancel", end);
  return off;
}

export type Sheet = { ref: RefObject<HTMLDivElement | null>; width: number; place: Place | null; usable: boolean; fold: () => void;
  attrs: Record<string, unknown> & { style: CSSProperties } };

export function useSheet(where: Where, t: Target, ready: boolean, close: () => void): Sheet {
  const ref = useRef<HTMLDivElement>(null);
  const [geo, setGeo] = useState<Geo | null>(null);
  const [place, setPlace] = useState<Place | null>(null);
  const [usable, setUsable] = useState(false);
  const shut = useRef(close);
  shut.current = close;
  const stop = useRef<(() => void) | null>(null), folding = useRef(false), words = useRef(0); // words: its height at open
  const from = place && geo?.anchor && where === "live" ? insetOf(fromInset(place, geo.anchor)) : "";
  const fold = useCallback(() => {
    const el = ref.current;
    if (folding.current) return;
    folding.current = true;
    setCover(where, null);
    if (!el || !from || hidden(el) || matchMedia("(prefers-reduced-motion: reduce)").matches) return shut.current();
    el.setAttribute("data-fold", "");
    if (still(el)) return shut.current();
    stop.current?.();
    stop.current = onEnd(el, () => shut.current());
  }, [where, from]);
  useLayoutEffect(() => { // at open: measured at its width, then placed once its words are read
    const el = ref.current;
    if (!el || place) return;
    if (!geo) return void setGeo(geoOf(el, where, t.id));
    if (!ready) return;
    words.current = el.offsetHeight;
    setPlace(where === "live" ? agentsPlace(geo.anchor, geo.view, words.current) : drawerPlace(geo.anchor, geo.view, geo.size, words.current));
  });
  useLayoutEffect(() => { // placed: it covers its part of the drawing; Agents' unfolds from its box
    const el = ref.current;
    if (!el || !place) return;
    setCover(where, el);
    if (!from || still(el)) return void setUsable(true);
    el.setAttribute("data-unfold", "");
    void el.offsetWidth; // its start drawn before the transition
    el.removeAttribute("data-unfold");
    stop.current = onEnd(el, () => setUsable(true));
  }, [place]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { // a zoom since the open folds it
    if (place && geo && !folding.current && zoomOf(geo.frame) !== geo.zoom) fold();
  });
  useEffect(() => { // what folds it: Escape, a pointer-down outside, a wheel over the drawing
    const el = ref.current, frame = geo?.frame, pan = frame?.querySelector<HTMLElement>("[data-pan]");
    if (!el || !frame || !place) return;
    const at = (n: EventTarget | null): SheetEvent["at"] => {
      const e = n instanceof Element ? n : null, inPan = e?.closest("[data-pan]");
      if (!e) return "else";
      if (el.contains(e)) return "sheet";
      if (e.closest(".scrim")) return "scrim";
      if (e.closest(SLOT) && frame.contains(e)) return "slot";
      if (inPan && frame.contains(inPan)) return e.closest(PICK) ? "pick" : "pan";
      return "else";
    };
    const go = (e: SheetEvent) => sheetClose(e) === "fold" && fold();
    const gone = () => ((folding.current = true), setCover(where, null), shut.current()); // its view went: closed at once
    const down = (e: PointerEvent) => (hidden(el) ? gone() : go({ kind: "pointer", at: at(e.target) }));
    const key = (e: KeyboardEvent) => hidden(el) || go({ kind: "key", at: at(e.target), key: e.key, field: !!(e.target as Element | null)?.closest?.("textarea, input") });
    const wheel = (e: WheelEvent) => go({ kind: "wheel", at: at(e.target) });
    const seen = new ResizeObserver(() => hidden(el) && gone()); // a hidden view sizes it 0 x 0: a section left by its key
    document.addEventListener("pointerdown", down, true);
    window.addEventListener("keydown", key);
    pan?.addEventListener("wheel", wheel, { passive: true });
    seen.observe(el);
    return () => (document.removeEventListener("pointerdown", down, true), window.removeEventListener("keydown", key), pan?.removeEventListener("wheel", wheel),
      seen.disconnect());
  }, [place, fold]); // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => () => (stop.current?.(), setCover(where, null)), []); // eslint-disable-line react-hooks/exhaustive-deps
  const style: CSSProperties = place ? { left: place.left, top: place.top, width: place.width, height: place.height, ...(from ? { ["--sheet-from" as string]: from } : {}) }
    : { left: 0, top: 0, width: geo?.width || undefined };
  const attrs = place ? { "data-place": where === "live" ? "sheet" : "drawer", "data-side": place.side, "data-words": words.current, "data-testid": usable ? "map-step-in" : undefined,
    "data-open": usable ? "" : undefined, inert: !usable, style } : { "data-place": "measure", inert: true, "aria-hidden": true, style };
  return { ref, width: geo?.width || 0, place, usable, fold, attrs };
}
