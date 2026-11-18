// The Map's top line's pieces (3.6.0.2 R55: the Map is the plan; 3.6.0.3 B: it never draws the past): the plan of the
// session the quiet line names and a goal run going (with Open). A running session is not drawn on the Map: its one
// quiet line is NoticeRow.tsx, its drawing Agents -> 4 · Live.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Button } from "../../../lib/ui";
import { isLiveRun, useOrch } from "../../orchestra/store";
import { openRun as openOrchRun, startOrchestra } from "../../orchestra/sync";
import { openFeed, openMapDrawer } from "./feedOpen";
import { planWords, startTodos, useTodos } from "./todoStore";
import { WORDS } from "./truthWords";

/** R4b: the plan of the session the quiet line names (`sid`), a door into 4 · Live's Feed. */
export function Extras({ sid }: { sid: string }) {
  useEffect(() => (startTodos(), startOrchestra()), []);
  const plan = planWords(useTodos(sid));
  if (!plan) return null;
  return (
    <span className="cw-line" data-testid="map-lit-extras">
      <button type="button" className="mp-link" onClick={() => openFeed("plan")} data-testid="map-lit-plan" title={`The session's plan, in 4 · ${WORDS.live}'s ${WORDS.feed}`}>{plan}</button>
    </span>
  );
}

/** R4b: a goal run going, with Open (its pages in the Map's drawer, opened at once and filled as its reads arrive: P4
 *  batch 9). P8 (the owner's rule: a text is never cut): the goal's whole words wrap beside Open, its own item that never
 *  shrinks, on the top line's own row. P8 repair (nothing moves after the first draw): the Map's canvas is drawn once the
 *  runs are listed (MapCanvas.tsx), so a run going is in the first draw; the row keeps the tallest room it has had, so a
 *  run ending moves nothing; a run started later (Run a goal) grows it once.
 *  P8 batch 3 (the coordinator's ruling): the run's room is there from the Map's FIRST draw, one line high, empty and
 *  not announced while no goal run exists: a line of its own under the top line's row of controls, the Map's whole
 *  width (MapBar.tsx TopLine; the repair: beside the button before it it had 319 px at 1500 x 900, and a 40-character goal took two
 *  lines). It costs the drawing that one line. A goal that fits the line moves nothing when it starts; a longer one
 *  grows the row once (its words are never cut). */
export function RunRow() {
  const run = useOrch((s) => s.runs.find((r) => isLiveRun(r.state)));
  const box = useRef<HTMLDivElement>(null);
  const [kept, setKept] = useState(0);
  useLayoutEffect(() => {
    const h = box.current?.offsetHeight || 0;
    if (h > kept + 0.5) setKept(h);
  });
  return (
    <div className="cw-line mp-run-row" data-testid="map-lit-run-row" ref={box} style={kept ? { minHeight: kept } : undefined}
         aria-hidden={run ? undefined : "true"}>
      {run ? <span className="mp-extras-run" data-testid="map-lit-run" data-run={run.run_id}>
        <span className="mp-extras-goal" data-testid="map-lit-run-goal">{GOING}{run.goal_what}</span>
        <Button size="sm" onClick={() => (openMapDrawer(`run:${run.run_id}`), void openOrchRun(run.run_id))} data-testid="map-lit-run-open"
                title="Its pages (lanes, the gate, the merge, its report) in the drawer">Open</Button>
      </span> : null}
    </div>
  );
}

const GOING = "A goal run is going: ";
