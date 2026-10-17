// team-feed (3.0.8.0 R2): the run's event lines (`events.jsonl`: kind,
// stage, text, elapsed), newest last, with a chip row that filters by kind
// (state / trigger / gate / claim / change; report and note lines always
// show). It follows the live frames: at the bottom it stays at the bottom.
// A click on a line with a stage selects that stage.
import { useEffect, useRef } from "react";
import type { MotionState } from "../../lib/motion";
import { Metric } from "../orchestra/bits";
import { select } from "./actions";
import { elapsed, FILTER_KINDS, FILTERS, team, useTeam, type FilterKey } from "./store";
import type { EventLine } from "./types";

function shown(e: EventLine, filter: Record<FilterKey, boolean>): boolean {
  const key = FILTERS.find((k) => FILTER_KINDS[k].includes(e.kind));
  return key ? filter[key] : true;
}

export function FeedDetail() {
  const events = useTeam((s) => s.events);
  const filter = useTeam((s) => s.filter);
  const run = useTeam((s) => s.eventsRun);
  const box = useRef<HTMLOListElement>(null);
  const atEnd = useRef(true);
  const list = events.filter((e) => shown(e, filter));
  useEffect(() => {
    const el = box.current;
    if (el && atEnd.current) el.scrollTop = el.scrollHeight;
  }, [list.length]);
  const toggle = (k: FilterKey) => team.update((s) => ({ filter: { ...s.filter, [k]: !s.filter[k] } }));
  return (
    <div className="tm-feed" data-testid="team-feed-body">
      <div className="tm-filters" role="group" aria-label="Show these kinds">
        {FILTERS.map((k) => (
          <button key={k} className="tm-filter mono" aria-pressed={filter[k]} data-kind={k} data-testid="team-filter" onClick={() => toggle(k)}
                  title={`${filter[k] ? "Hide" : "Show"} the ${k} lines`}>{k}</button>
        ))}
        <span className="spacer" />
        <span className="mono muted">{run ? `run ${run} · ${events.length} lines` : "no run yet"}</span>
      </div>
      {list.length ? (
        <ol className="tm-events" ref={box} onScroll={(e) => {
          const el = e.currentTarget;
          atEnd.current = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
        }}>
          {list.map((e, i) => (
            <li key={`${e.ts}-${i}`} className="tm-event" data-testid="team-event" data-kind={e.kind} data-stage={e.stage || undefined}
                onClick={() => e.stage && select({ kind: "stage", id: e.stage })}>
              <span className="mono muted tm-ev-t">+{elapsed(e.elapsed_s)}</span>
              <span className="og-chip mono tm-ev-kind" data-kind={e.kind}>{e.kind}</span>
              {e.stage && <b className="mono tm-ev-stage">{e.stage}</b>}
              <span className="tm-ev-text">{e.text}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted tm-feed-empty">{events.length ? "Every line is filtered out: turn a chip back on." : "Nothing has happened yet: Run next starts the first manual stage, and every move lands here."}</p>
      )}
    </div>
  );
}

export function FeedGlance() {
  const n = useTeam((s) => s.events.length);
  const last = useTeam((s) => s.events[s.events.length - 1]);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={n} label="lines" />
      </div>
      <div className="glance-hint">{last ? `${last.kind}: ${last.text}` : "Expand for every move of the run."}</div>
    </div>
  );
}

export function useFeedMotion(): MotionState {
  return useTeam((s) => (s.board?.state === "open" && s.live ? "live" : s.events.length ? "idle" : "none"));
}
