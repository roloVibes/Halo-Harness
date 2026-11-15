// Live's "Run a goal" button and panel (3.4.0.0 D "the runs fold": the goal form as a panel beside the canvas; Runs'
// Start screen before, which is gone -- no screen of its own). The button sits on Live's bar; the panel is closed on
// load, opens on its click (or the palette's "Agents: Run a goal", History's "Run it again", the Pack Manager's Run
// <workflow>), closes on its x, Esc, the button again or a run that started -- the run is then on Live (a dry run's jobs
// in History). Inside: the goal form (GoalForm.tsx: what you want, when it is done, the shared files, the gate's test,
// Review the plan first, then what it will do, what it may cost and where it writes), "Run it across the fleet" while
// another machine is paired, and "or run a pack's workflow" (its form takes the goal form's place).
import { useEffect } from "react";
import { Button } from "../../../lib/ui";
import { GoalForm } from "../../orchestra/GoalForm";
import { WorkflowForm } from "../../orchestra/WorkflowForm";
import { WorkflowPicker } from "../../orchestra/WorkflowPicker";
import { useOrch } from "../../orchestra/store";
import { useWfRun } from "../../orchestra/workflowRun";
import { openReport } from "../live/historyStore";
import { closeGoal, toggleGoal, useGoal } from "./goalStore";

export function RunGoalButton() {
  const open = useGoal((s) => s.open);
  const live = useOrch((s) => (s.data?.live ? s.runId : ""));
  return (
    <Button size="sm" variant="ghost" className={open ? "on" : ""} aria-pressed={open} onClick={toggleGoal} data-testid="live-run-goal"
            title={live ? `Run a goal: run ${live} is live, so the form opens and Run waits for it to end` : "Run a goal: give the lineup a goal; it runs here as lanes under a lead, and its report lands in History"}>
      Run a goal
    </Button>
  );
}

export function GoalDrawer() {
  const open = useGoal((s) => s.open);
  const seed = useGoal((s) => s.seed);
  const form = useGoal((s) => s.form);
  const wf = useWfRun((s) => s.wf);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !(e.target as HTMLElement | null)?.closest?.("[role=listbox], [role=menu], [role=dialog], .mpk") && (e.stopPropagation(), closeGoal());
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open]);
  if (!open) return null;
  const started = (id: string, dry: boolean) => {
    closeGoal();
    if (dry && id) void openReport(id); // a dry run ends at once: the lead's jobs are its report page
  };
  return (
    <aside className="lh-drawer rg-drawer" data-testid="run-goal-drawer" aria-label="Run a goal">
      <div className="lh-head" data-density="bar">
        <b className="lh-title">{wf ? `Run the workflow ${wf.name}` : "Run a goal"}</b>
        <span className="mono muted">several agents, one goal, one set of files</span>
        <span className="spacer" />
        <button className="icon-btn" onClick={closeGoal} aria-label="Close Run a goal" title="Close (Esc): nothing is run" data-testid="run-goal-close">×</button>
      </div>
      <div className="rg-body">
        {wf ? <WorkflowForm onStarted={closeGoal} /> : (
          <>
            <GoalForm initial={form} seed={seed} onStarted={started} />
            <WorkflowPicker />
          </>
        )}
      </div>
    </aside>
  );
}
