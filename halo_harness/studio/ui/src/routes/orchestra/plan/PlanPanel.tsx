// orchestra-plan (3.0.9.0 R2): the one panel that takes the run console's
// place while the open run is `planned` (its goal said "Review the plan
// before it runs"). The toolbar, the canvas (the lanes in their layer boxes),
// the inspector of the selected lane, the problems; Approve and run hands the
// plan to the waiting run and the console comes back. The Roles bios and the
// model catalog are read once for the inspector's pickers.
import { useEffect } from "react";
import type { MotionState } from "../../../lib/motion";
import type { PanelSpec } from "../../../lib/workspace/types";
import { HELP } from "../../help";
import { loadLists, loadModels } from "../../roles/sync";
import { roles } from "../../roles/store";
import { Metric } from "../bits";
import { useOrch } from "../store";
import { PlanBar, PlanProblems, RejectCard } from "./Bar";
import { PlanCanvas } from "./Canvas";
import { PlanInspector } from "./Inspector";
import { layerMap, loadPlan } from "./actions";
import { usePlan } from "./store";

function usePlanLoad(): void {
  const runId = useOrch((s) => s.runId);
  useEffect(() => {
    if (runId) void loadPlan(runId);
  }, [runId]);
  useEffect(() => {
    const r = roles.get();
    if (!r.loaded) void loadLists();
    if (!r.modelsLoaded) void loadModels();
  }, []);
}

export function PlanDetail() {
  usePlanLoad();
  const loaded = usePlan((s) => s.loaded);
  const n = usePlan((s) => s.jobs.length);
  if (!loaded) return <div className="og-wait mono muted">reading the plan...</div>;
  return (
    <div className="pc" data-testid="plan-editor">
      <PlanBar />
      <RejectCard />
      <div className="pc-main">
        {n ? <PlanCanvas /> : <div className="pc-scroll pc-empty muted" data-testid="plan-canvas">No lanes: Add lane, or Reject the plan.</div>}
        <aside className="pc-side">
          <PlanInspector />
        </aside>
      </div>
      <PlanProblems />
    </div>
  );
}

export function PlanGlance() {
  usePlanLoad();
  const jobs = usePlan((s) => s.jobs);
  const problems = usePlan((s) => s.problems.length);
  const layers = new Set(Object.values(layerMap(jobs))).size;
  return (
    <div className="glance">
      <div className="glance-kicker mono">THE PLAN WAITS FOR YOU</div>
      <div className="glance-numbers">
        <Metric value={jobs.length} label="lanes" />
        <Metric value={layers} label="layers" />
        <Metric value={problems} label="problems" tone={problems ? "bad" : "ok"} />
      </div>
      <div className="glance-hint">Expand to edit it, then Approve and run.</div>
    </div>
  );
}

function usePlanMotion(): MotionState {
  const problems = usePlan((s) => s.problems.length);
  return problems ? "error" : "waiting";
}

export const planPanels: PanelSpec[] = [
  { id: "orchestra-plan", testid: "orchestra-plan", title: "Plan", ...HELP["orchestra-plan"], x: 0, y: 0, w: 24, h: 0, minW: 12, minH: 40,
    face: "detail", glance: PlanGlance, detail: PlanDetail, useMotion: usePlanMotion },
];
