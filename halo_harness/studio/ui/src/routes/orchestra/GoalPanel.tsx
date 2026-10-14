// Goal: the full face = the open run in one line over its goal form (Run and
// Dry run in view at the default size); the compact face = the three fields
// as a card (what / done when / stop when), the workers, the cost and the run
// state badge; Settings = the run to open. The runs of the repo are in the
// rail and on the Start view.
import { Button } from "../../lib/ui";
import { type MotionState } from "../../lib/motion";
import { Metric, NoRun, StateBadge } from "./bits";
import { cost, short } from "./format";
import { GoalForm } from "./GoalForm";
import { runMotion, setView, useOrch } from "./store";
import { openRun, stopRun } from "./sync";

function Field3({ label, text, n }: { label: string; text: string; n: number }) {
  return (
    <div className="og-goal-field">
      <span className="og-goal-label mono">{label}</span>
      <span className="og-goal-text" title={text}>
        {short(text, n) || "-"}
      </span>
    </div>
  );
}

export function GoalGlance() {
  const data = useOrch((s) => s.data);
  const runs = useOrch((s) => s.runs.length);
  if (!data)
    return (
      <div className="glance">
        <NoRun what="The goal" />
        <Button variant="primary" onClick={() => setView("start")}>
          Write a goal
        </Button>
      </div>
    );
  const g = data.goal;
  return (
    <div className="glance og-goal">
      <div className="glance-row">
        <StateBadge state={data.run.state} />
        <div className="glance-numbers og-goal-numbers">
          <Metric value={g.workers} label="workers" />
          <Metric value={cost(data.run.cost_usd)} label="cost" />
        </div>
      </div>
      <div className="og-goal-card">
        <Field3 label="WHAT YOU WANT" text={g.what} n={110} />
        <Field3 label="DONE WHEN" text={g.done_when} n={70} />
        <Field3 label="STOP WHEN" text={g.stop_when} n={70} />
      </div>
      <div className="glance-hint mono">
        run {data.run.run_id} · {g.files.join(", ") || "no files"} · {runs} run{runs === 1 ? "" : "s"} in this repo
        {data.live && (
          <>
            {" · "}
            <button className="og-link" onClick={() => void stopRun()}>
              stop
            </button>
          </>
        )}
      </div>
    </div>
  );
}

export function GoalDetail() {
  return <GoalForm />;
}

export function GoalSettings() {
  const runs = useOrch((s) => s.runs);
  const current = useOrch((s) => s.runId);
  return (
    <label className="field">
      <span className="field-label mono">OPEN RUN</span>
      <select className="input mono" value={current} onChange={(e) => void openRun(e.target.value)}>
        {runs.map((r) => (
          <option key={r.run_id} value={r.run_id}>
            {r.run_id} · {r.state}
          </option>
        ))}
      </select>
    </label>
  );
}

export function useGoalMotion(): MotionState {
  const state = useOrch((s) => s.data?.run.state);
  const doneAt = useOrch((s) => s.doneAt);
  return runMotion(state, doneAt);
}
