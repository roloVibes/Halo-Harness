// Where the Fleet section's panels landed (3.3.16.0 R2 "the Fleet fold": a machine's agents in Agents, its models in
// Local, machines in Setup). Every old door that named a Fleet panel -- an attention row's `o`, the palette, a pack's
// route, Settings' and Setup's links -- comes through `showFleetPanel` and opens the new home:
//   fleet-mission                       Agents -> Runs, the Mission panel (fleetPanels.ts)
//   fleet-attention                     Agents, the Attention panel (attention.ts)
//   fleet-activity                      Agents -> Live, the Activity panel
//   fleet-agent                         Agents -> Live, the agent in the inspector
//   fleet-ollama | ollama               Local -> Hosts
//   fleet-people | -costs | -health | -capabilities | -map | -tree   Agents -> Live on the fleet, the machine picked
import { goSection } from "../../lib/store";
import { patchPanel, showPanel, whenLaidOut } from "../../lib/workspace/persist";
import { panels } from "../fleet/pstore";
import { openAgentPanel } from "../fleet/actions";
import { fleet, localId } from "../fleet/store";
import { goto as gotoLocal } from "../local/pages";
import { setView as setRunsView } from "../orchestra/store";
import { setAttention } from "./attention";
import { activityPanel, missionPanel } from "./fleetPanels";
import { clearPick, pickLive, setScope } from "./live/scope";

/** Run `go` once the workspace `section` has laid out (it mounts its layout first; however long a slow box takes). */
const whenLaid = whenLaidOut;

/** Agents -> Runs with the Mission panel up (the mission itself: fleet/mload.ts openMission). */
export function openMissionPanel(): void {
  goSection("agents", "runs");
  setRunsView("workspace"); // the panels, even before the runs are read (a door at load) or with none open
  whenLaid("orchestra", () => showPanel("orchestra", missionPanel));
}

/** Agents -> Live with the Activity panel beside the tree. */
export function openActivity(): void {
  goSection("agents", "live");
  whenLaid("roles", () => showPanel("roles", activityPanel));
}

/** Agents -> Live on the fleet; with `machine`, that machine in the inspector (else the fleet at a glance, opened when
 *  "while you were away" waits there: the rail's dot, the palette). */
export function openFleetLive(machine = ""): void {
  setScope("fleet");
  goSection("agents", "live");
  if (machine) return pickLive("machine", machine);
  clearPick();
  if (panels.get().digestOpen) whenLaid("roles", () => patchPanel("roles", "roles-inspector", { collapsed: false, face: "detail" }, false));
}

/** Local -> Hosts, on `host` when named (the steward's attention row, Settings' and Setup's links). */
export function openLocalHost(host = ""): void {
  gotoLocal("hosts", host || undefined);
  goSection("local");
}

export function showFleetPanel(id: string, machine = ""): void {
  if (id === "fleet-mission") return openMissionPanel();
  if (id === "fleet-attention") return (goSection("agents"), setAttention(true));
  if (id === "fleet-activity") return openActivity();
  if (id === "fleet-agent") {
    const k = fleet.get().selected;
    if (k && !k.startsWith(`${localId()}|`)) setScope("fleet"); // another machine's agent: Live on the fleet
    return openAgentPanel(k || undefined);
  }
  if (id === "fleet-ollama" || id === "ollama") return openLocalHost();
  openFleetLive(machine);
}
