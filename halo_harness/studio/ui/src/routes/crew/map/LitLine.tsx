// The Map's top line's pieces (3.6.0.2 R55: the Map is the plan): a replay of History's run says what plays, in quiet
// colours, with Back to now; with nothing replaying, "Replay the last session" and a goal run going (with Open). A
// running session is not drawn on the Map: its one quiet line is NoticeRow.tsx, its drawing Agents -> 4 · Live.
import { useEffect } from "react";
import { Button } from "../../../lib/ui";
import { isLiveRun, useOrch } from "../../orchestra/store";
import { openRun as openOrchRun, startOrchestra } from "../../orchestra/sync";
import { openFeed, openMapDrawer } from "./feedOpen";
import { planWords, startTodos, useTodos } from "./todoStore";
import { closeRun, replayRun, useMapHist } from "./mapRuns";
import { useMap } from "./mapStore";

/** R4b (R4's gap 9): with a finished run in History, the top line offers to replay it. Before there is one its room is
 *  kept (an unseen twin), so a session ending -- History's first row -- never moves the drawing under the line (R55). */
export function ReplayLast() {
  const last = useMapHist((s) => s.rows[0]);
  return last ? <> <Button size="sm" onClick={() => void replayRun(last.sid)} data-testid="map-lit-replay-last" title={`Replay "${last.what.slice(0, 60)}" on the map`}>Replay the last session</Button></>
    : <> <button type="button" tabIndex={-1} aria-hidden="true" className="btn btn-default btn-sm mp-kept"><span className="btn-label">Replay the last session</span></button></>;
}

/** R4b: the plan of the session the quiet line names (`sid`), a door into 4 · Live's Feed; a goal run going, with Open (its
 *  pages in the Map's drawer, opened at once and filled as its reads arrive: P4 batch 9). Its buttons live in ONE parent
 *  whatever the line beside them says, so a listing landing never takes a button away under a click (batch 9). */
export function Extras({ sid }: { sid: string }) {
  useEffect(() => (startTodos(), startOrchestra()), []);
  const plan = planWords(useTodos(sid));
  const run = useOrch((s) => s.runs.find((r) => isLiveRun(r.state)));
  if (!plan && !run) return null;
  return (
    <span className="cw-line" data-testid="map-lit-extras">
      {plan && <button type="button" className="mp-link" onClick={() => openFeed("plan")} data-testid="map-lit-plan" title="The session's plan, in 4 · Live's Feed">{plan}</button>}
      {plan && run && " · "}
      {run && <span data-testid="map-lit-run" data-run={run.run_id}>
        A goal run is going: {run.goal_what.slice(0, 80)}{" "}
        <Button size="sm" onClick={() => (openMapDrawer(`run:${run.run_id}`), void openOrchRun(run.run_id))} data-testid="map-lit-run-open"
                title="Its pages (lanes, the gate, the merge, its report) in the drawer">Open</Button>
      </span>}
    </span>
  );
}

/** A replay of History's run on the Map (R55: a replay stays on the Map), with Back to now. */
export function ReplayLine() {
  const shown = useMap((s) => s.name);
  const run = useMapHist((s) => s.open);
  return (
    <p className="cw-line mp-topline">
      Replaying {run?.title ? `"${run.title.slice(0, 60)}"` : "a past session"} {run?.map ? (run.map === shown ? "on this map" : `(it ran on ${run.map})`) : "(it did not start on a map)"}, in quiet colours.{" "}
      <Button size="sm" onClick={closeRun} data-testid="map-replay-close">Back to now</Button>
    </p>
  );
}
