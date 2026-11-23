// Session's drawer head holds still while the drawing is held (3.6.0.15 F12, R12's rule for the head): while the pointer
// rests on the drawing or a card is open (hold.ts), the head keeps the height it had when the hold began and its status
// line keeps the room it had (map-down.css .mp-head-held): the words change in place; a line that needs another row
// takes it when the hold ends, in the same re-flow that draws everything else that waited. Held short, the whole line
// is the hover (`title`) of the status words' own box (3.6.0.16 U3: never of the head, so a button of the head keeps its
// own hover). No timer, no observer, no listener: the heights are read once, at the render the hold begins (the drawn
// head, before anything of the hold is drawn), and kept in a ref until it ends.
// 3.6.0.16 U2: THE SAME RULE, FOR THE SLOT UNDER THE DRAWING (MapDown.tsx's "more below" and the wait link): held, it
// keeps its height and the wait link's row its room (.mp-below-held), so the drawing's scroll box keeps its height; the
// link's words change in place and their whole line is the link's own hover (runWait.tsx WaitLink's `title`).
import { useLayoutEffect, useRef, type CSSProperties, type RefObject } from "react";

const SAID = ".mp-status-box", LINE = ".mp-status", WAIT = ".mp-wait-row";

/** `cls` goes after the held element's own classes, `style` on it. */
export type HeadHold = { cls: string; style?: CSSProperties };
type Held = HeadHold & { ref: RefObject<HTMLDivElement | null> };

/** Holds `el`'s height and the room of its part `room` while `held`; `line`: the words inside `room` whose whole text is
 *  `room`'s hover when they are held short (null: they carry their own hover). */
export function useHeadHold(el: RefObject<HTMLElement | null>, held: boolean, room = SAID, line: string | null = LINE,
                            cls = " mp-head-held"): HeadHold {
  const kept = useRef<{ h: number; said: number } | null>(null);
  if (!held) kept.current = null;
  else if (!kept.current && el.current) {
    const e = el.current;
    kept.current = { h: e.offsetHeight, said: e.querySelector<HTMLElement>(room)?.offsetHeight || 0 };
  }
  useLayoutEffect(() => { // held short: the line is taller than the room it keeps, so the whole of it is the room's hover
    const box = line ? el.current?.querySelector<HTMLElement>(room) : null;
    if (!box) return;
    const p = held && kept.current?.said ? box.querySelector<HTMLElement>(line!) : null;
    const t = p && p.offsetHeight > box.clientHeight + 0.5 ? p.textContent || "" : "";
    if (t && box.title !== t) box.title = t;
    else if (!t && box.hasAttribute("title")) box.removeAttribute("title");
  });
  const k = kept.current;
  if (!k) return { cls: "" };
  const said = k.said ? ({ "--mp-said-h": `${k.said}px` } as CSSProperties) : {};
  return { cls: k.said ? cls : "", style: { height: k.h, ...said } };
}

/** The drawer's two held parts: its head (its status line's room) and the slot under the drawing (the wait link's row). */
export function useDrawerHold(held: boolean): { head: Held; below: Held } {
  const head = useRef<HTMLDivElement>(null), below = useRef<HTMLDivElement>(null);
  return { head: { ref: head, ...useHeadHold(head, held) }, below: { ref: below, ...useHeadHold(below, held, WAIT, null, " mp-below-held") } };
}
