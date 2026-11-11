// "Run it across the fleet" (3.3.16.0 R2 "the Fleet fold": a mission is the goal form's fleet twin): under the goal form
// of Live's Run a goal panel (3.4.0.0 D; Runs' Start view before), only while more than one harness is paired; it opens
// the Mission panel's Start form on Live. A running mission is drawn on Live's fleet scope and a finished one is a row of
// History (3.4.0.0 D: Runs' mission rows and its "+" menu's went with Runs).
import { Button } from "../../../lib/ui";
import { newMission } from "../../fleet/mload";
import { useFleet } from "../../fleet/store";

export function AcrossTheFleet() {
  const many = useFleet((s) => s.harnesses.length > 1 && s.pack);
  if (!many) return null;
  return (
    <div className="ag-across">
      <Button size="sm" variant="ghost" onClick={newMission} data-testid="runs-across-fleet"
              title="One goal for every paired machine: the hub's lead splits it into parts by what each machine can do (the Mission panel)">
        Run it across the fleet
      </Button>
    </div>
  );
}
