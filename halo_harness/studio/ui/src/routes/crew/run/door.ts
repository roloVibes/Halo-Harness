// Where a goal run opens (3.6.0.0 R5: Live went; the Map's drawer holds a run's pages): while it runs -- or waits on you
// for its plan -- its pages (crew/run/RunInspector.tsx) in the Map's drawer; once it ended, its report as a page of
// History in the same drawer. Every door that names a run comes here: `&run=<id>` in the URL, an attention row's `o`
// (an Orchestra gate, a supervisor decision), the palette's run lines.
import { goSection } from "../../../lib/store";
import { orch, isLiveRun } from "../../orchestra/store";
import { loadRuns, openRun as openOrchRun, startOrchestra } from "../../orchestra/sync";
import { openReport } from "../live/historyStore";
import { openMapDrawer } from "../map/feedOpen";
import { openGoalHere, type GoalForm } from "./goalStore";

/** The run of `id` (an exact id or a unique prefix), read afresh when the list does not hold it. */
async function rowOf(id: string) {
  const find = () => orch.get().runs.filter((r) => r.run_id === id || r.run_id.startsWith(id));
  let hits = find();
  if (hits.length !== 1) {
    await loadRuns();
    hits = find();
  }
  return hits.find((r) => r.run_id === id) || (hits.length === 1 ? hits[0] : null);
}

/** Open a run where it is: its pages in the Map's drawer while it runs or waits for its plan, else its report. The
 *  drawer opens FIRST (a run the list holds as live, or one it does not hold yet: the run's pages say they are reading)
 *  and is filled as the reads arrive; a read that never ends fails at its limit (lib/apiLimit.ts), never a closed door. */
export async function openRun(id: string): Promise<void> {
  startOrchestra();
  goSection("agents", "map");
  const known = orch.get().runs.find((r) => r.run_id === id);
  if (!known || isLiveRun(known.state)) openMapDrawer(`run:${id}`);
  const row = known || await rowOf(id);
  if (row && isLiveRun(row.state)) {
    if (row.run_id !== id) openMapDrawer(`run:${row.run_id}`); // a prefix named it
    if (orch.get().runId !== row.run_id) void openOrchRun(row.run_id);
    return;
  }
  void openReport(row?.run_id || id);
  openMapDrawer("history");
}

/** An Orchestra worker's session (its cwd is the lane's worktree, `.halo/orchestra/<run>/wt/worker-<n>`): its run. */
export function openWorkerRun(cwd: string): void {
  const m = /orchestra[\\/]([0-9]{8}-[0-9]{6}-[0-9a-f]{4})[\\/]wt[\\/]worker-[0-9]+/.exec(cwd || "");
  void openRun(m ? m[1] : orch.get().runId);
}

/** The Map with the goal form in its drawer (with `form`, those fields filled in). */
export function openGoal(form?: GoalForm): void {
  goSection("agents", "map");
  openGoalHere(form);
  openMapDrawer("goal");
}
