// The faces of a finished run's report (3.0.9.0 R3 in Coach.tsx; 3.4.0.0 B2: the Coach tab left with the coach
// pack, its Coach panel in Agents): Report, and a workflow run's Artifacts (3.2.0.0 R5).
import { Tabs } from "../../lib/ui";

export type ReportTab = "report" | "artifacts";

export function ReportTabs({ value, onChange, artifacts }: { value: ReportTab; onChange: (t: ReportTab) => void; artifacts: number }) {
  const items = [{ id: "report", label: "Report", testid: "report-tab-report" },
                 { id: "artifacts", label: `Artifacts (${artifacts})`, testid: "report-tab-artifacts", title: "The workflow's typed outputs" }];
  return <Tabs label="Report or artifacts" value={value} onChange={(id) => onChange(id as ReportTab)} items={items} />;
}
