// The Orchestra section before a run is open: one centered Start view
// instead of eight empty panels -- the goal form with examples, what a run
// does in five numbered steps (the section help's copy), and the past runs
// to open (the shared Start view pattern). OrchestraView decides between it
// and the panel workspace, which comes up once a run starts or is opened,
// or with "open the workspace anyway". 3.0.9.0 R2: while the open run is
// `planned` the plan panel (plan/PlanPanel.tsx) takes the console's place.
// 3.2.0.0 R6: while the Pack Manager's Run <workflow> has filled one in, the
// workflow's form (WorkflowForm.tsx) shows instead of the goal form; 3.2.1.0
// R2: with none, the picker under the goal form (WorkflowPicker.tsx) fills one.
import { useEffect } from "react";
import { Surface } from "../../lib/ui";
import { Workspace } from "../../lib/workspace/Workspace";
import type { PanelSpec } from "../../lib/workspace/types";
import { SECTION_HELP } from "../sectionHelp";
import { GoalForm } from "./GoalForm";
import { WorkflowForm } from "./WorkflowForm";
import { WorkflowPicker } from "./WorkflowPicker";
import { useWfRun } from "./workflowRun";
import { PastRuns } from "./OrchRail";
import { planPanels } from "./plan/PlanPanel";
import { usePlan } from "./plan/store";
import { loadingFirst, setView, showsStart, useOrch } from "./store";
import { startOrchestra } from "./sync";
import { NextStep } from "../NextStep";

export function StartView() {
  const copy = SECTION_HELP.orchestra;
  const error = useOrch((s) => s.error);
  const wf = useWfRun((s) => s.wf); // 3.2.0.0 R6: a pack's workflow from the Pack Manager's Run
  return (
    <div className="fl-start og-start" data-testid="start-view">
      <div className="fl-start-inner">
        <header className="fl-start-head">
          <div className="glance-kicker mono">ORCHESTRA · SEVERAL AGENTS, ONE GOAL</div>
          <h1 className="fl-start-title">{wf ? `Run the workflow ${wf.name}` : "Start a run"}</h1>
          <p className="muted">{copy.what}</p>
        </header>
        <div className="fl-start-grid">
          <Surface className="fl-start-form" motion="idle">
            {wf ? (
              <WorkflowForm />
            ) : (
              <>
                <GoalForm start />
                <WorkflowPicker />
              </>
            )}
          </Surface>
          <aside className="fl-start-side">
            <ol className="fl-explain">
              {copy.steps.map(([title, text], i) => (
                <li key={title}>
                  <span className="fl-explain-n mono" data-gate={title.includes("gate") || undefined}>
                    {i + 1}
                  </span>
                  <span>
                    <b>{title}</b>
                    <span className="fl-explain-text">{text}</span>
                  </span>
                </li>
              ))}
            </ol>
            {error && <p className="og-problems">Studio could not read the runs: {error}</p>}
            <PastRuns />
            <button className="og-link mono" onClick={() => setView("workspace")} data-testid="orchestra-open-workspace">
              open the workspace anyway
            </button>
          </aside>
        </div>
        <NextStep from="orchestra" />
      </div>
    </div>
  );
}

/** The Orchestra section: the Start view until a run is open, then the panels. */
export function OrchestraView({ section, specs }: { section: string; specs: PanelSpec[] }) {
  useEffect(() => startOrchestra(), []);
  const start = useOrch(showsStart);
  const waiting = useOrch(loadingFirst);
  const planned = useOrch((s) => s.data?.run.state === "planned");
  const runId = useOrch((s) => s.runId);
  const staged = usePlan((s) => !!s.staged && s.runId === runId); // 3.0.9.0 R3: a coach edit staged
  if (start) return <StartView />;
  if (waiting)
    return (
      <div className="fl-start">
        <div className="og-wait mono muted">reading the runs of this repo...</div>
      </div>
    );
  if (planned || staged) return <Workspace section="orchestra-plan" specs={planPanels} />; // 3.0.9.0 R2: the plan canvas
  return <Workspace section={section} specs={specs} />;
}
