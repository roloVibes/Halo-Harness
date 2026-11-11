// Agents -> Live's inspector (3.3.16.0 R2 "the Fleet fold"; R1b's summary first), by what is picked on the tree:
// nothing -- the fleet at a glance (FleetGlance.tsx); a machine -- its summary (MachineSummary.tsx); an agent -- the one
// agent inspector (routes/fleet/Agent.tsx AgentView, inside Roles' Live tab wrapper so `roles-live` /
// `roles-live-agent` stay where they were); a mission part -- its card (PartCard.tsx); 3.4.0.0 D a goal run's lead or a
// lane -- the run's summary and its pages (routes/agents/run/RunInspector.tsx). A click on the canvas itself clears the
// pick; Back on a picked thing does too.
import { Button } from "../../../lib/ui";
import { Watched } from "../../roles/LiveTab";
import { FleetGlance } from "./FleetGlance";
import { MachineSummary } from "./MachineSummary";
import { PartCard } from "./PartCard";
import { RunInspector } from "../run/RunInspector";
import { clearPick, useLivePick } from "./scope";

function Back() {
  return (
    <div className="lv-back" data-density="bar">
      <Button size="sm" variant="ghost" onClick={clearPick} data-testid="live-inspector-back" title="The fleet at a glance">All machines</Button>
    </div>
  );
}

export function LiveInspector() {
  const pick = useLivePick();
  return (
    <div className="lv-inspector" data-testid="live-inspector" data-pick={pick.kind || "none"}>
      {pick.kind && <Back />}
      {pick.kind === "machine" ? <MachineSummary hid={pick.id} />
        : pick.kind === "part" ? <PartCard id={pick.id} />
        : pick.kind === "run" || pick.kind === "lane" ? <RunInspector kind={pick.kind} id={pick.id} />
        : pick.kind === "agent" || pick.kind === "session" ? (
          <div className="rl" data-testid="roles-live" data-view="live">
            <Watched k={pick.id} />
          </div>
        ) : <FleetGlance />}
    </div>
  );
}
