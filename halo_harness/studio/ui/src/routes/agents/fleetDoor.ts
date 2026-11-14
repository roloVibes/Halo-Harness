// Where the live panels' old doors land (their ids kept). Every door that names one -- an attention row's `o`, the
// palette, a pack's route, Settings' and Setup's links -- comes through `showFleetPanel` and opens its home:
//   fleet-attention                     Agents, the Attention panel (attention.ts)
//   fleet-activity                      Agents -> Live, the Activity panel
//   fleet-agent                         Agents -> Live, the agent in the inspector
//   fleet-ollama | ollama               Local -> Hosts
//   anything else (fleet-costs, ...)    Agents -> Live, this halo at a glance in the inspector
import { goSection } from "../../lib/store";
import { showPanel, whenLaidOut } from "../../lib/workspace/persist";
import { openAgentPanel } from "../fleet/actions";
import { fleet } from "../fleet/store";
import { goto as gotoLocal } from "../local/pages";
import { setAttention } from "./attention";
import { activityPanel } from "./fleetPanels";
import { clearPick } from "./live/scope";

/** Agents -> Live with the Activity panel beside the tree. */
export function openActivity(): void {
  goSection("agents", "live");
  whenLaidOut("roles", () => showPanel("roles", activityPanel));
}

/** Local -> Hosts, on `host` when named (the steward's attention row, Settings' and Setup's links). */
export function openLocalHost(host = ""): void {
  gotoLocal("hosts", host || undefined);
  goSection("local");
}

export function showFleetPanel(id: string): void {
  if (id === "fleet-attention") return (goSection("agents"), setAttention(true));
  if (id === "fleet-activity") return openActivity();
  if (id === "fleet-agent") return openAgentPanel(fleet.get().selected || undefined);
  if (id === "fleet-ollama" || id === "ollama") return openLocalHost();
  clearPick();
  goSection("agents", "live");
}
