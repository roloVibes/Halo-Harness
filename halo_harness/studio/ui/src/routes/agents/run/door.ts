// Where a goal run opens (3.4.0.0 D "the runs fold"): while it runs -- or waits on you for its plan -- it is a job on
// Live: Agents on Live, this halo's scope, the run's lead picked (the inspector on the run, summary first); once it
// ended, its report as a page of History. Every door that names a run comes here: `&run=<id>` in the URL, an attention
// row's `o` (an Orchestra gate, a supervisor decision), the palette's run lines, a lane's node menu.
import { goSection } from "../../../lib/store";
import { orch, isLiveRun } from "../../orchestra/store";
import { loadRuns, openRun as openOrchRun, startOrchestra } from "../../orchestra/sync";
import { openReport } from "../live/historyStore";
import { pickLive } from "../live/scope";

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

/** Open a run where it is: on Live while it runs or waits for its plan, its report in History once it ended. */
export async function openRun(id: string, lane?: number): Promise<void> {
  startOrchestra();
  goSection("agents", "live");
  const row = await rowOf(id);
  if (row && isLiveRun(row.state)) {
    if (orch.get().runId !== row.run_id) await openOrchRun(row.run_id);
    pickLive(lane ? "lane" : "run", lane ? `${row.run_id}:${lane}` : row.run_id);
    return;
  }
  openReport(row?.run_id || id);
}

/** An Orchestra worker's session (its cwd is the lane's worktree, `.halo/orchestra/<run>/wt/worker-<n>`): its run. */
export function openWorkerRun(cwd: string): void {
  const m = /orchestra[\\/]([0-9]{8}-[0-9]{6}-[0-9a-f]{4})[\\/]wt[\\/]worker-([0-9]+)/.exec(cwd || "");
  void openRun(m ? m[1] : orch.get().runId, m ? Number(m[2]) : undefined);
}
