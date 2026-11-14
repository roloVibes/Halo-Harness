// Agents -> Live's inspector (R1b's summary first), by what is picked on the tree: nothing -- this halo at a glance
// (LiveGlance.tsx); an agent -- the one agent inspector (routes/fleet/Agent.tsx AgentView, inside Roles' Live tab
// wrapper so `roles-live` / `roles-live-agent` stay where they were); 3.4.0.0 D a goal run's lead or a lane -- the run's
// summary and its pages (routes/agents/run/RunInspector.tsx). A click on the canvas itself clears the pick; Back on a
// picked thing does too.
import { Button } from "../../../lib/ui";
import { Watched } from "../../roles/LiveTab";
import { LiveGlance } from "./LiveGlance";
import { RunInspector } from "../run/RunInspector";
import { clearPick, useLivePick } from "./scope";

function Back() {
  return (
    <div className="lv-back" data-density="bar">
      <Button size="sm" variant="ghost" onClick={clearPick} data-testid="live-inspector-back" title="This halo at a glance">Back</Button>
    </div>
  );
}

export function LiveInspector() {
  const pick = useLivePick();
  return (
    <div className="lv-inspector" data-testid="live-inspector" data-pick={pick.kind || "none"}>
      {pick.kind && <Back />}
      {pick.kind === "run" || pick.kind === "lane" ? <RunInspector kind={pick.kind} id={pick.id} />
        : pick.kind === "agent" || pick.kind === "session" ? (
          <div className="rl" data-testid="roles-live" data-view="live">
            <Watched k={pick.id} />
          </div>
        ) : <LiveGlance />}
    </div>
  );
}
