// 3.6.0.23 PV (the owner: "We need to add that what the objective is and what it's doing"): under the Feed head's
// session row, ONE row there from the first draw -- "Objective" and main's objective (his row's `objective`: the first
// line of his latest prompt of four words or more; wrapping, never cut) and, at its end, the plan chip: "Plan 3 of 7"
// with a plan, muted "no plan yet" without (before main's first list, and after a resume). Its hover says the step in
// progress. Under it the plan written out (crew/map/PlanList.tsx, the Feed's own list), open while a plan exists and the
// person has not folded it; a click on the chip folds and unfolds it, kept (planFold.ts). Its opening when the first
// plan arrives is the one move; no plan, no list. The words are crew/map/planWords.ts; nothing here asks a model.
import { PlanList } from "../crew/map/PlanList";
import { chipHover, chipWords, objectiveOf, planOf } from "../crew/map/planWords";
import { useWatched } from "./ChangeSession";
import { togglePlanFold, usePlanFolded } from "./planFold";

export function FeedPlan() {
  const { row } = useWatched();
  const list = planOf(row), objective = objectiveOf(row);
  const folded = usePlanFolded();
  const open = list.length > 0 && !folded;
  return (
    <>
      <div className="slv-objective" data-testid="session-feed-objective">
        <span className="slv-objective-words">
          <span className="slv-objective-label mono">Objective</span>
          {objective ? <span data-testid="session-objective-words">{objective}</span>
            : <span className="muted" data-testid="session-objective-none" title="The first line of your latest prompt of four words or more shows here">none yet</span>}
        </span>
        <button type="button" className="slv-plan-chip mono" data-testid="session-plan-chip"
                aria-disabled={list.length ? undefined : "true"} aria-expanded={list.length ? open : undefined} title={chipHover(list)}
                onClick={() => list.length && togglePlanFold()}>
          {chipWords(list)}
        </button>
      </div>
      {open && <div className="slv-plan" data-testid="session-plan"><PlanList list={list} tid="session-plan-list" /></div>}
    </>
  );
}
