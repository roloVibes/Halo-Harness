// Where the live panels' old doors land (their ids kept). Every door that names one -- an attention row's `o`, the
// palette, a pack's route, Settings' and Setup's links -- comes through `showFleetPanel` and opens its home (3.6.0.2 R52:
// a run is watched on Agents -> 4 · Live again; lib/agentsDoor.ts panelDoor decides, node-tested):
//   fleet-attention                     Agents, the Attention panel (attention.ts)
//   fleet-agent                         Agents -> Map, the agent's rows in the drawer (3.6.0.1: an ask of a session
//                                       of this harness opens in Session instead, glance/openAsk.ts)
//   fleet-ollama | ollama               Local -> Hosts
//   anything else (fleet-activity, fleet-costs, ...)    Agents -> Live
import { goSection } from "../../lib/store";
import { panelDoor } from "../../lib/agentsDoor";
import { openAgentPanel } from "../fleet/actions";
import { fleet } from "../fleet/store";
import { goto as gotoLocal } from "../local/pages";
import { setAttention } from "./attention";
import { clearPick } from "../crew/live/scope";

/** Local -> Hosts, on `host` when named (the steward's attention row, Settings' and Setup's links). */
export function openLocalHost(host = ""): void {
  gotoLocal("hosts", host || undefined);
  goSection("local");
}

export function showFleetPanel(id: string): void {
  const to = panelDoor(id);
  if (to === "attention") return (goSection("agents"), setAttention(true));
  if (to === "agent") return openAgentPanel(fleet.get().selected || undefined);
  if (to === "local") return openLocalHost();
  clearPick(); // R34: the scope is cleared off Session
  goSection("agents", "live");
}
