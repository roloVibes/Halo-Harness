// Session's drawer head holds still while the drawing is held (3.6.0.15 F12, R12's rule for the head): while the pointer
// rests on the drawing or a card is open (hold.ts), the head keeps the height it had when the hold began and its status
// line keeps the room it had (map-down.css .mp-head-held): the words change in place; a line that needs another row
// takes it when the hold ends, in the same re-flow that draws everything else that waited. Held short, the whole line
// is the head's hover (`title`). No timer, no observer, no listener: the heights are read once, at the render the hold
// begins (the drawn head, before anything of the hold is drawn), and kept in a ref until it ends.
import { useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

const SAID = ".mp-status-box", LINE = ".mp-status";

/** `cls` goes after the head's own classes; `style` and `title` on the head itself. */
export type HeadHold = { cls: string; style?: CSSProperties; title?: string };

export function useHeadHold(head: RefObject<HTMLElement | null>, held: boolean): HeadHold {
  const kept = useRef<{ h: number; said: number } | null>(null);
  if (!held) kept.current = null;
  else if (!kept.current && head.current) {
    const el = head.current;
    kept.current = { h: el.offsetHeight, said: el.querySelector<HTMLElement>(SAID)?.offsetHeight || 0 };
  }
  const [title, setTitle] = useState<string>();
  useLayoutEffect(() => { // held short: the line is taller than the room it keeps, so the whole of it is the hover
    const box = held && kept.current?.said ? head.current?.querySelector<HTMLElement>(SAID) : null;
    const p = box?.querySelector<HTMLElement>(LINE);
    const t = box && p && p.offsetHeight > box.clientHeight + 0.5 ? p.textContent || undefined : undefined;
    setTitle((o) => (o === t ? o : t));
  });
  const k = kept.current;
  if (!k) return { cls: "" };
  const said = k.said ? ({ "--mp-said-h": `${k.said}px` } as CSSProperties) : {};
  return { cls: k.said ? " mp-head-held" : "", style: { height: k.h, ...said }, title };
}
