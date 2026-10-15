// The palette's mission commands (3.0.6.0 R8), in the Fleet group:
// "Fleet: new mission" (the Mission panel's goal box, focused), "Fleet:
// approve mission" (the open or newest planned one), "Fleet: stop mission"
// (the running one: the stop dialog asks for a reason), "Fleet: mission
// report" (the open one, else the newest).
import { toast } from "../../lib/store";
import { short } from "../orchestra/format";
import type { FleetCommand } from "./commands";
import { FINAL, LIVE, missions, type Summary } from "./mstore";
import { approve, newMission, openMission, setFace } from "./mload";

function find(test: (m: Summary) => boolean): Summary | null {
  const s = missions.get();
  const list = s.list || [];
  return list.find((m) => m.id === s.open && test(m)) || list.find(test) || null;
}

export function missionCommands(g: string, inFleet: (fn: () => void) => () => void): FleetCommand[] {
  const planned = find((m) => m.state === "planned");
  const running = find((m) => LIVE.includes(m.state));
  const latest = find((m) => FINAL.includes(m.state)) || find(() => true);
  return [
    { id: "fleet-mission-new", group: g, label: "Fleet: new mission", hint: "one goal for the whole fleet; the hub's lead splits it by what each harness can do (M opens the panel)", run: inFleet(newMission) },
    {
      id: "fleet-mission-approve", group: g, label: "Fleet: approve mission", hint: planned ? short(planned.goal, 60) : "no plan waits for approval",
      run: inFleet(() => {
        if (!planned) return toast("No mission waits for approval", "info");
        openMission(planned.id);
        void approve();
      }),
    },
    {
      id: "fleet-mission-stop", group: g, label: "Fleet: stop mission", hint: running ? `asks first · ${short(running.goal, 50)}` : "no mission runs",
      run: inFleet(() => {
        if (!running) return toast("No mission runs now", "info");
        openMission(running.id);
        missions.update(() => ({ stopAsk: true }));
      }),
    },
    {
      id: "fleet-mission-report", group: g, label: "Fleet: mission report", hint: latest ? short(latest.goal, 60) : "no mission yet",
      run: inFleet(() => {
        if (!latest) return toast("No mission yet: Fleet: new mission starts one", "info");
        openMission(latest.id);
        setFace("report");
      }),
    },
  ];
}
