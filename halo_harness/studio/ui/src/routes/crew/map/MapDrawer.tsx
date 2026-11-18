// 3 · Map's right drawer (3.6.0.2 R57 with R42): the Feed went to 4 · Live, and the pages it carried for the Map stay
// here -- Run a goal's form (`goal`, crew/run/GoalDrawer.tsx), a goal run's pages (`run:<id>`, crew/run/RunInspector.tsx)
// and a finished goal run's report (`report:<id>`, crew/run/ReportPage.tsx; 3.6.0.3 B). Opened by Run a goal, a goal
// run's door, or its own button in the view bar (on Run a goal's form, which his opening opens with it). 3.6.0.3 B:
// History and its lists left Studio. A page's own close (its ×, Esc) closes the drawer with it: the drawer never stays
// open on nothing.
import { useEffect, useRef } from "react";
import { Button } from "../../../lib/ui";
import { layoutStore, patchPanel } from "../../../lib/workspace/persist";
import { GoalDrawer } from "../run/GoalDrawer";
import { goal, openGoalHere, useGoal } from "../run/goalStore";
import { ReportPage } from "../run/ReportPage";
import { RunInspector } from "../run/RunInspector";
import { MAP_DRAWER, MAP_SECTION, mapPage, mapPageTitle, useMapPage } from "./feedOpen";

export function MapDrawerGlance() {
  const page = useMapPage();
  return <div className="glance"><div className="glance-hint">{mapPageTitle(page)}: expand it.</div></div>;
}

/** His opening of the drawer (its view-bar button, the palette's Show panel) on Run a goal's page opens the form with
 *  it. A drawer open from the first draw (a saved layout, `?open=all`) does not: it offers the form (nothing opens by
 *  itself). MapView calls it once. */
export function useGoalOnOpen(): void {
  useEffect(() => {
    const st = layoutStore(MAP_SECTION);
    let laid = st.get().layout !== null, was = st.get().layout?.[MAP_DRAWER]?.collapsed;
    return st.subscribe(() => {
      const now = st.get().layout?.[MAP_DRAWER]?.collapsed;
      if (laid && was !== false && now === false && mapPage() === "goal" && !goal.get().open) openGoalHere();
      laid = st.get().layout !== null;
      was = now;
    });
  }, []);
}

/** Run a goal's page with the form closed (the drawer open from the first draw): one line and the form's own button. */
function GoalOffer() {
  return (
    <p className="cw-line" data-testid="map-drawer-goal-offer">
      Run a goal: several agents, one goal, one set of files.{" "}
      <Button size="sm" onClick={() => openGoalHere()} data-testid="map-drawer-goal-open">Run a goal</Button>
    </p>
  );
}

export function MapDrawer() {
  const page = useMapPage();
  const goalOpen = useGoal((s) => s.open);
  const shown = page === "goal" ? goalOpen : true;
  const was = useRef({ shown, page });
  useEffect(() => { // the page closed itself (its × or Esc), not another page taking its place: the drawer closes with it
    const before = was.current;
    was.current = { shown, page };
    if (before.shown && !shown && before.page === page && layoutStore(MAP_SECTION).get().layout?.[MAP_DRAWER]?.collapsed !== true)
      patchPanel(MAP_SECTION, MAP_DRAWER, { collapsed: true }, false);
  }, [shown, page]);
  return (
    <div className="mpf" data-testid="map-drawer" data-page={page}>
      <div className="mpf-page">{page === "goal" ? (goalOpen ? <GoalDrawer /> : <GoalOffer />)
        : page.startsWith("report:") ? <ReportPage id={page.slice(7)} /> : <RunInspector kind="run" id={page.slice(4)} />}</div>
    </div>
  );
}
