// One square on the board (3.3.16.0 R3): the name, then four mono lines -- DOES / TAKES / GIVES / COSTS -- and a limits
// chip; nothing else. The full contract shows in the inspector on select, never on the card. The `x` is the only way off
// the board; it says what changed in the board's one line. The square at work glows (one at a time). 3.3.16.1: resting
// the pointer on it (or the arrows moving the keyboard's focus to it) shows its hover card (routes/agents/hover/
// square.tsx) in place of the inspector-on-hover and the lines' titles; with `studio.hover_cards` off, as before.
import { useEffect, useRef, type MouseEvent } from "react";
import { useHover } from "../../../lib/hover/useHover";
import { SquareHover } from "../hover/square";
import type { Box } from "./Edges";
import { disableSquare, select, setHover, type Square } from "./store";

type Props = { sq: Square; box: Box; working: boolean; selected: boolean; focused: boolean };

const LINES: [string, (q: Square) => string][] = [
  ["DOES", (q) => q.does || "-"],
  ["TAKES", (q) => q.takes.join(", ") || "text"],
  ["GIVES", (q) => q.gives.join(", ") || "-"],
  ["COSTS", (q) => q.costs],
];

export function Card({ sq, box, working, selected, focused }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const hv = useHover("square", sq.ref, () => <SquareHover sqRef={sq.ref} />);
  const t = hv.titles;
  useEffect(() => { // the arrows' focus is the keyboard's: its card after the same wait, gone when it moves or is opened
    if (!focused || selected) return;
    hv.show(el.current);
    return hv.hide;
  }, [focused, selected]);
  const off = (e: MouseEvent) => (e.stopPropagation(), void disableSquare(sq.ref));
  return (
    <div ref={el} className="wf-card" role="button" tabIndex={-1} data-testid="wf-card" data-ref={sq.ref} data-engine={sq.engine}
         data-glow={working || undefined} data-selected={selected || undefined} data-focus={focused || undefined}
         style={{ left: box.x, top: box.y, width: box.w, height: box.h }} aria-label={`${sq.ref}: ${sq.does}`}
         onClick={() => select(sq.ref)} onMouseEnter={t ? () => setHover(sq.ref) : undefined} {...hv.props}>
      <div className="wf-card-head">
        <b className="wf-card-name mono" data-testid="wf-card-name" title={t ? sq.ref : undefined}>{sq.ref}</b>
        <button className="icon-btn wf-card-x" onClick={off} aria-label={`Take ${sq.ref} off the board`}
                title={`Take ${sq.ref} off the board (disable it for this lineup)`} data-testid="wf-card-x">×</button>
      </div>
      <dl className="wf-card-lines">
        {LINES.map(([label, text]) => (
          <div key={label} data-line={label.toLowerCase()}>
            <dt className="mono">{label}</dt>
            <dd className="mono" title={t ? text(sq) : undefined}>{text(sq)}</dd>
          </div>
        ))}
      </dl>
      <span className="wf-chip mono" data-testid="wf-card-limits" data-hover-skip title="The square's limits: how deep it may hand off, its turns and its wall time">
        {sq.limits}
      </span>
    </div>
  );
}
