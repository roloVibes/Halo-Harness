// What a goal run will do, what it may cost and where it writes -- said under the goal form before Run (3.4.0.0 D; the
// owner's rule for every offered action: what / cost / time / writes, nothing paid hidden). Composed from the form as
// it stands (the workers, the return cap, the test, Review the plan first, the model) and what the lead resolves to;
// no request. docs/ORCHESTRA.md "The files on disk" is where the run's record lives.
import type { RunForm } from "../../orchestra/sync";

const plural = (n: number, one: string) => `${n} ${one}${n === 1 ? "" : "s"}`;

export function GoalSays({ form, lead }: { form: RunForm; lead: string }) {
  const n = Math.max(1, form.workers || 1);
  const worker = form.model || `the ${form.worker || "worker"} role's model`;
  const leadOn = form.model || lead || `the ${form.lead || "lead"} role's model`;
  const test = form.test.trim() ? `runs \`${form.test.trim()}\`` : "runs the lineup's test, if it names one";
  return (
    <dl className="rg-says" data-testid="run-goal-says">
      <dt>WHAT IT DOES</dt>
      <dd data-testid="run-goal-does">
        The lead ({leadOn}) splits the goal into up to {plural(n, "lane")}; each lane's worker edits the units it claims in
        its own worktree; the lanes merge one at a time and the gate {test} and checks DONE WHEN, sending a part back up
        to {plural(form.return_cap, "time")}. {form.review ? "It stops after the split: the plan waits for you on Live (Review the plan on its lead) before anything is claimed." : "It shows on Live as it runs; its report lands in History."}
      </dd>
      <dt>WHAT IT MAY COST</dt>
      <dd data-testid="run-goal-cost">
        One call for the lead's split, then one worker session per lane on {worker}, again for each part sent back. A goal
        run has no dollar cap: its budget is {plural(n, "lane")} and the return cap. {form.review ? "The plan shows each lane's cost forecast before it runs." : "Review the plan first shows a forecast before anything is spent."} Dry run is the split alone: one call.
      </dd>
      <dt>WHERE IT WRITES</dt>
      <dd data-testid="run-goal-writes">
        The run's record in <code>.halo/orchestra/&lt;run&gt;/</code> of this repo (never committed), one git worktree and
        branch per lane and the finished branch <code>orchestra/&lt;run&gt;</code>; your checkout is not touched: the
        finished branch is yours to merge.
      </dd>
    </dl>
  );
}
