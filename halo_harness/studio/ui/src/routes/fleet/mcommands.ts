// The palette's mission commands (3.0.6.0 R8; 3.3.16.0 R2: missions are the Mission panel on Agents -> Live):
// "Agents: new mission" (the Mission panel's goal box, focused), "Agents: approve mission" (the open or newest
// planned one), "Agents: stop mission" (the running one: the stop dialog asks for a reason), "Agents: mission
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

export function missionCommands(g: string): FleetCommand[] {
  const inRuns = (fn: () => void) => fn; // each opens the Mission panel in Runs itself (mload.ts openMission, newMission)
  const planned = find((m) => m.state === "planned");
  const running = find((m) => LIVE.includes(m.state));
  const latest = find((m) => FINAL.includes(m.state)) || find(() => true);
  return [
    { id: "fleet-mission-new", group: g, label: "Agents: new mission", hint: "one goal for the whole fleet; the hub's lead splits it by what each machine can do", run: inRuns(newMission) },
    {
      id: "fleet-mission-approve", group: g, label: "Agents: approve mission", hint: planned ? short(planned.goal, 60) : "no plan waits for approval",
      run: inRuns(() => {
        if (!planned) return toast("No mission waits for approval", "info");
        openMission(planned.id);
        void approve();
      }),
    },
    {
      id: "fleet-mission-stop", group: g, label: "Agents: stop mission", hint: running ? `asks first · ${short(running.goal, 50)}` : "no mission runs",
      run: inRuns(() => {
        if (!running) return toast("No mission runs now", "info");
        openMission(running.id);
        missions.update(() => ({ stopAsk: true }));
      }),
    },
    {
      id: "fleet-mission-report", group: g, label: "Agents: mission report", hint: latest ? short(latest.goal, 60) : "no mission yet",
      run: inRuns(() => {
        if (!latest) return toast("No mission yet: Agents: new mission starts one", "info");
        openMission(latest.id);
        setFace("report");
      }),
    },
  ];
}
