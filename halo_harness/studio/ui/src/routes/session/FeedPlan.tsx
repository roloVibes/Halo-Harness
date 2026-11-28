// 3.6.0.23 PV (the owner: "We need to add that what the objective is and what it's doing"). After the first CI run
// (the coordinator's ruling): the plan view takes no height from the Feed unless the person asks for it.
// FeedPlanBar sits in the Feed panel's TITLE BAR (Session.tsx `bar`, lib/workspace/Panel.tsx), after the panel's own
// words: "Objective" and main's objective (his row's `objective`: the first line of his latest prompt of four words or
// more) on ONE line in the free width, ending with an ellipsis when it does not fit (its hover says it whole), then the
// plan chip: "Plan 3 of 7" with a plan, muted "no plan yet" without (its hover the step in progress). The bar keeps its
// height. FeedPlan, in the Feed's head, is the plan written out (crew/map/PlanList.tsx), CLOSED until the person clicks
// the chip (planFold.ts, kept): open, it starts with the objective whole (wrapping). A plan arriving while it is closed
// moves nothing. The words are crew/map/planWords.ts; nothing here asks a model.
import type { SyntheticEvent } from "react";
import { PlanList } from "../crew/map/PlanList";
import { chipHover, chipWords, countOf, objectiveOf, planOf } from "../crew/map/planWords";
import { useWatched } from "./ChangeSession";
import { togglePlanFold, usePlanFolded } from "./planFold";

const NONE_HOVER = "The first line of your latest prompt of four words or more shows here";
const keep = (e: SyntheticEvent) => e.stopPropagation(); // a fast second click on the chip is not the bar's double-click

function Objective({ text, tid }: { text: string; tid: string }) {
  return text ? <span data-testid={tid}>{text}</span> : <span className="muted" data-testid="session-objective-none" title={NONE_HOVER}>none yet</span>;
}

export function FeedPlanBar() {
  const { row } = useWatched();
  const list = planOf(row), objective = objectiveOf(row), count = countOf(row, list); // the true counts of the whole list
  const folded = usePlanFolded(); // every draw calls it (a hook)
  const open = list.length > 0 && !folded;
  return (
    <span className="slv-bar-plan" data-testid="session-feed-objective" onDoubleClick={keep}>
      <span className="slv-objective-line" title={objective || undefined}>
        <span className="slv-objective-label mono">Objective</span>
        <Objective text={objective} tid="session-objective-words" />
      </span>
      <button type="button" className="slv-plan-chip mono" data-testid="session-plan-chip"
              aria-disabled={list.length ? undefined : "true"} aria-expanded={list.length ? open : undefined} title={chipHover(list, count)}
              onClick={() => list.length && togglePlanFold()}>
        {chipWords(list, count)}
      </button>
    </span>
  );
}

export function FeedPlan() {
  const { row } = useWatched();
  const list = planOf(row), objective = objectiveOf(row), count = countOf(row, list);
  const folded = usePlanFolded();
  if (!list.length || folded) return null;
  return (
    <div className="slv-plan" data-testid="session-plan">
      <div className="slv-plan-objective" data-testid="session-plan-objective">
        <span className="slv-objective-label mono">Objective</span>
        <Objective text={objective} tid="session-plan-objective-words" />
      </div>
      <PlanList list={list} all={count.all} tid="session-plan-list" />
    </div>
  );
}
