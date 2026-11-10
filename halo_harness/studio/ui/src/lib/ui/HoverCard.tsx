// The one hover card of the page (3.3.16.1, docs/STUDIO-shell.md "The hover card"): mounted once by the shell, drawn
// beside the box lib/hover/store.ts says it describes, measured after it draws and kept wholly inside the window
// (lib/hover/place.ts, NodeMenu's technique), re-placed when its content changes size. `role="tooltip"`, the box carries
// `aria-describedby`; the pointer may move onto it (its text can be selected) and it holds no buttons -- the actions are
// the inspector's and the box's "..." menu. It goes when its box leaves the page or the section hides it.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { place, type Spot } from "../hover/place";
import { CARD_ID, hideHover, hideSoon, hover, installHoverListeners, keepHover } from "../hover/store";
import { studio, useStore } from "../store";

type At = Spot & { id: string };

export function HoverCardHost() {
  const shown = useStore(hover, (s) => s.shown);
  const section = useStore(studio, (s) => s.section);
  const box = useRef<HTMLDivElement>(null);
  const [at, setAt] = useState<At | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => installHoverListeners(), []);
  useEffect(() => hideHover(), [section]);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el || !shown) return;
    const a = shown.el.getBoundingClientRect();
    if (!shown.el.isConnected || (a.width === 0 && a.height === 0)) return hideHover(shown.id);
    const p = place(a, el.offsetWidth, el.offsetHeight, window.innerWidth, window.innerHeight);
    if (!at || at.id !== shown.id || at.left !== p.left || at.top !== p.top || at.side !== p.side) setAt({ ...p, id: shown.id });
  });
  useEffect(() => {
    const el = box.current;
    if (!el || !shown) return;
    const ro = new ResizeObserver(() => setTick((t) => t + 1)); // its rows changed: place it again
    ro.observe(el);
    return () => ro.disconnect();
  }, [shown]);
  if (!shown) return null;
  const placed = at && at.id === shown.id;
  const leave = (e: { relatedTarget: EventTarget | null }) => {
    if (e.relatedTarget instanceof Node && shown.el.contains(e.relatedTarget)) return;
    hideSoon(shown.id);
  };
  return createPortal(
    <div ref={box} id={CARD_ID} role="tooltip" className="hover-card" data-testid="hover-card" data-kind={shown.kind} data-for={shown.key}
         data-side={placed ? at.side : undefined} data-by={shown.by} data-tick={tick}
         style={{ left: placed ? at.left : 0, top: placed ? at.top : 0, visibility: placed ? "visible" : "hidden" }}
         onPointerEnter={keepHover} onPointerLeave={leave}>
      {shown.render()}
    </div>,
    document.body,
  );
}
