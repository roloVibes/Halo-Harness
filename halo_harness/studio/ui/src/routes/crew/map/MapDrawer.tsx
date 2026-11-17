// 3 · Map's right drawer (3.6.0.2 R57 with R42): the Feed went to 4 · Live, and the pages it carried for the Map stay
// here -- Run a goal's form (`goal`, crew/run/GoalDrawer.tsx), a goal run's pages (`run:<id>`, crew/run/RunInspector.tsx)
// and History's whole list (`history`: sessions, goal runs, saved replay files, two ticked -> Compare; live/History.tsx).
// Opened by Run a goal, History's "Goal runs, files, Compare", a goal run's door, or its own button in the view bar (on
// History). A replay opened from the Map's History lists its rows on History's page, up to the scrubber (P4 batch 12:
// FeedParts.tsx ReplayRows, brought back from the Map's old feed drawer). A page's own close (its ×, Esc) closes the drawer with it: the drawer never stays open on nothing.
import { useEffect, useRef } from "react";
import { layoutStore, patchPanel } from "../../../lib/workspace/persist";
import { HistoryDrawer } from "../live/History";
import { history, toggleHistory, useHistory } from "../live/historyStore";
import { GoalDrawer } from "../run/GoalDrawer";
import { useGoal } from "../run/goalStore";
import { RunInspector } from "../run/RunInspector";
import { MAP_DRAWER, MAP_SECTION, mapPageTitle, useMapPage } from "./feedOpen";
import { ReplayRows } from "./FeedParts";
import { useLitNow } from "./useLit";

export function MapDrawerGlance() {
  const page = useMapPage();
  return <div className="glance"><div className="glance-hint">{mapPageTitle(page)}: expand it.</div></div>;
}

export function MapDrawer() {
  const page = useMapPage();
  const goalOpen = useGoal((s) => s.open);
  const histOpen = useHistory((s) => s.open);
  const L = useLitNow();
  const shown = page === "goal" ? goalOpen : page === "history" ? histOpen : true;
  useEffect(() => { // opened from its own button on History: History's list opens with it
    if (page === "history" && !history.get().open) toggleHistory(true);
  }, [page]);
  const was = useRef({ shown, page });
  useEffect(() => { // the page closed itself (its × or Esc), not another page taking its place: the drawer closes with it
    const before = was.current;
    was.current = { shown, page };
    if (before.shown && !shown && before.page === page && layoutStore(MAP_SECTION).get().layout?.[MAP_DRAWER]?.collapsed !== true)
      patchPanel(MAP_SECTION, MAP_DRAWER, { collapsed: true }, false);
  }, [shown, page]);
  return (
    <div className="mpf" data-testid="map-drawer" data-page={page}>
      {page === "history" && L.mode === "replay" && <div className="mpf-replay" data-testid="map-drawer-replay"><ReplayRows L={L} ids={null} /></div>}
      <div className="mpf-page">{page === "goal" ? <GoalDrawer /> : page === "history" ? <HistoryDrawer /> : <RunInspector kind="run" id={page.slice(4)} />}</div>
    </div>
  );
}
