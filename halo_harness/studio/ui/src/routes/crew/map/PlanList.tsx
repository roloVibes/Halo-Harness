// A session's plan written out (3.6.0.0 R4b's list in the Feed's `plan` page; 3.6.0.23 PV: the same list under Session's
// head): one line per step, its state as a mark AND a word (planWords.ts STEP), the step in progress standing out with
// its activeForm words. Every line holds the room of both its forms (the twin), so a change of state never changes the
// list's height while the number of steps is the same. More than PLAN_ROWS steps: the list scrolls in its own box and
// keeps the step in progress in view (its own scrollTop only: nothing around it moves). 3.6.0.23 PV after the review:
// where step numbers are left out (a list over the row's cap: `all` is the whole list's count) ONE muted line says how
// many, in that place (planWords.ts planLines).
import { useLayoutEffect, useRef } from "react";
import { moreWords, PLAN_ROWS, planLines, STEP, stepText, type Todo } from "./planWords";

export function PlanList({ list, all, tid = "map-feed-plan" }: { list: Todo[]; all?: number; tid?: string }) {
  const box = useRef<HTMLOListElement>(null);
  const lines = planLines(list, all);
  const now = lines.findIndex((l) => "step" in l && l.step.status === "in_progress");
  const long = list.length > PLAN_ROWS;
  useLayoutEffect(() => {
    const el = box.current, row = now >= 0 ? (el?.children[now] as HTMLElement | undefined) : undefined;
    if (!el || !row || !long) return;
    const top = row.offsetTop - el.offsetTop, bottom = top + row.offsetHeight;
    if (top < el.scrollTop) el.scrollTop = top;
    else if (bottom > el.scrollTop + el.clientHeight) el.scrollTop = bottom - el.clientHeight;
  }, [now, long, lines.length]);
  return (
    <ol className="mpf-plan" data-testid={tid} data-long={long ? "" : undefined} ref={box} aria-label="The plan">
      {lines.map((l, i) => {
        if (!("step" in l)) return <li key={i} className="mpf-plan-row mpf-plan-more muted" data-testid={`${tid}-more`}>{moreWords(l.more)}</li>;
        const t = l.step, st = STEP[t.status] || STEP.pending, w = stepText(t);
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
