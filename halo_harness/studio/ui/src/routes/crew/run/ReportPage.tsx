// A finished goal run's report as its own page of the Map's drawer (3.6.0.3 B: `report:<id>`, titled "Goal run").
// Opened by every door to a finished run (crew/run/door.ts openRunReport: `&run=<id>`, Attention's `o`,
// the palette's "Goal run <id>", a dry run, the run page's "Open its report"). Back returns to the run's page when that
// page's "Open its report" sent him here, else closes the drawer.
import { useEffect } from "react";
import { closeMapDrawer, openMapDrawer } from "../map/feedOpen";
import { loadRunReport, useRunReport } from "./reportStore";
import { RunReport } from "./RunReport";

export function ReportPage({ id }: { id: string }) {
  const got = useRunReport((s) => s);
  useEffect(() => { // the page shown without its door's read (none today): read it here, never a page that waits forever
    if (got.id !== id) void loadRunReport(id);
  }, [id, got.id]);
  const back = got.id === id ? got.back : "";
  const onBack = () => (back ? openMapDrawer(back) : closeMapDrawer());
  return (
    <div className="lh-drawer" data-testid="run-report-page" data-run={id}>
      <div className="lh-rows lh-page">
        {got.id === id && got.report ? <RunReport data={got.report} onBack={onBack} backTitle={back ? "Back to the run's page" : "Close the report (the drawer closes)"} />
          : got.id === id && got.error ? <p className="field-error" data-testid="history-report-error">Run {id}: {got.error}</p>
          : <div className="mono muted lh-note">reading run {id}...</div>}
      </div>
    </div>
  );
}
