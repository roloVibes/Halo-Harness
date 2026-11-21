// The palette's Run a workflow (3.6.0.6 P): a pick opens the same Run it form in the view he is in -- docked over the
// view's lower right corner, so nothing of the view moves and nothing navigates; it is the form, not a dialog (no
// scrim, the view stays usable). It closes with its Cancel, or once Watch it in Live is pressed.
import { useRunForm, cancelRun } from "./runFlowStore";
import { RunItForm } from "./RunFlow";

export const DOCK = "palette";

export function RunDock() {
  const name = useRunForm((s) => (s.at.startsWith(DOCK + ":") ? s.name : ""));
  const started = useRunForm((s) => !!s.sid);
  if (!name) return null;
  return (
    <div className="rf-dock" data-testid="run-flow-dock" onClickCapture={(e) => {
      if (started && (e.target as Element).closest?.("[data-testid=run-flow-watch]")) window.setTimeout(cancelRun, 0);
    }}>
      <RunItForm name={name} where={DOCK} />
    </div>
  );
}
