// The Report panel's Coach tab (3.0.9.0 R3): once a run has its report, the
// post-run coach's cards for it (GET orchestra/<run>/coach, lib/coach): what
// to change in a bio's prompt, model or tools, in the plan's structure, or in
// how the run was coordinated, each with the evidence from the run's files.
// Apply opens the editor that owns the change (coachApply.ts).
import { CoachCards } from "../../lib/coach/CoachCards";
import { Tabs } from "../../lib/ui";
import { applySuggestion } from "./coachApply";
import { useOrch } from "./store";

export type ReportTab = "report" | "coach";

export function CoachTab() {
  const runId = useOrch((s) => s.runId);
  return runId ? <CoachCards kind="orchestra" run={runId} onEdit={applySuggestion} /> : null;
}

/** The two faces of a finished run's report; the coach tab names how many cards it has once read. */
export function ReportTabs({ value, onChange }: { value: ReportTab; onChange: (t: ReportTab) => void }) {
  return (
    <Tabs label="Report or coach" value={value} onChange={(id) => onChange(id as ReportTab)}
          items={[{ id: "report", label: "Report", testid: "report-tab-report" },
                  { id: "coach", label: "Coach", testid: "report-tab-coach", title: "What the run's files suggest changing" }]} />
  );
}
