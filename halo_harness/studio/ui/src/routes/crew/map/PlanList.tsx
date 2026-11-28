// A session's plan written out (3.6.0.0 R4b's list in the Feed's `plan` page; 3.6.0.23 PV: the same list under Session's
// head): one line per step, its state as a mark AND a word (planWords.ts STEP), the step in progress standing out with
// its activeForm words. Every line holds the room of both its forms (the twin), so a change of state never changes the
// list's height while the number of steps is the same. More than PLAN_ROWS steps: the list scrolls in its own box and
// keeps the step in progress in view (its own scrollTop only: nothing around it moves).
import { useLayoutEffect, useRef } from "react";
import { PLAN_ROWS, STEP, stepText, type Todo } from "./planWords";

export function PlanList({ list, tid = "map-feed-plan" }: { list: Todo[]; tid?: string }) {
  const box = useRef<HTMLOListElement>(null);
  const now = list.findIndex((t) => t.status === "in_progress");
  const long = list.length > PLAN_ROWS;
  useLayoutEffect(() => {
    const el = box.current, row = now >= 0 ? (el?.children[now] as HTMLElement | undefined) : undefined;
    if (!el || !row || !long) return;
    const top = row.offsetTop - el.offsetTop, bottom = top + row.offsetHeight;
    if (top < el.scrollTop) el.scrollTop = top;
    else if (bottom > el.scrollTop + el.clientHeight) el.scrollTop = bottom - el.clientHeight;
  }, [now, long, list.length]);
  return (
    <ol className="mpf-plan" data-testid={tid} data-long={long ? "" : undefined} ref={box} aria-label="The plan">
      {list.map((t, i) => {
        const st = STEP[t.status] || STEP.pending, w = stepText(t);
        return (
          <li key={i} className="mpf-plan-row" data-testid={`${tid}-row`} data-status={t.status}>
            <span className="mono mpf-plan-state"><span aria-hidden="true">{st.mark}</span> {st.word}</span>
            <span className="mpf-plan-text">
              <span className="mpf-plan-words" data-testid={`${tid}-words`}>{w.text}</span>
              <span className="mpf-plan-twin" aria-hidden="true">{w.twin}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
