// Missions are Runs (3.3.16.0 R2 "the Fleet fold"): Runs' list -- the header's "+" menu's RUNS group and the Start view's
// past runs -- shows this machine's Orchestra runs and the fleet's missions as one list, newest first, each row saying
// which it is and where it runs ("run · this machine", "mission · parts on pc, kali"). A mission row opens the Mission
// panel in Runs on it (fleet/mload.ts openMission). On the Start view, with more than one harness paired, "Run it
// across the fleet" opens the Mission panel's Start form (the goal form's fleet twin); with one harness it does not
// show.
import { useEffect } from "react";
import type { MenuRow } from "../../../lib/ui/Menu";
import { Button } from "../../../lib/ui";
import { newMission, openMission, startMissions } from "../../fleet/mload";
import { LIVE, partMotion, useMissions, usd, type Summary } from "../../fleet/mstore";
import { useFleet } from "../../fleet/store";
import { clock, short } from "../../orchestra/format";

/** "mission · parts on pc, kali" (a mission's parts run on these machines). */
export function whereLine(m: Summary): string {
  return `mission · ${m.harnesses.length ? `parts on ${m.harnesses.join(", ")}` : "no machine yet"}`;
}

/** The missions, newest first (read once Runs shows; the feed keeps them current). */
export function useMissionList(): Summary[] {
  useEffect(() => startMissions(), []);
  const list = useMissions((s) => s.list);
  return [...(list || [])].sort((a, b) => b.created - a.created);
}

/** The "+" menu's mission rows (beside the runs). */
export function missionMenuRows(list: Summary[], open: string): MenuRow[] {
  return list.slice(0, 8).map((m) => ({
    id: "mission-" + m.id,
    label: short(m.goal, 34) || m.id,
    icon: "fleet",
    badges: [m.state],
    word: m.id === open ? "open now" : "open",
    current: m.id === open,
    title: `${m.id} · ${m.goal} · ${whereLine(m)} · ${usd(m.cost_usd)} · ${clock(m.created)}`,
    testid: "orchestra-menu-mission",
    data: { mission: m.id },
    run: () => openMission(m.id),
  }));
}

/** The Start view's mission rows, under its past runs. */
export function MissionRows() {
  const list = useMissionList();
  const running = list.filter((m) => LIVE.includes(m.state)).length;
  if (!list.length) return null;
  return (
    <section className="fl-start-runs" aria-label="Fleet missions" data-testid="runs-missions" data-running={running}>
      <div className="rail-label mono">MISSIONS · {list.length}{running ? ` · ${running} RUNNING` : ""}</div>
      {list.slice(0, 6).map((m) => (
        <button key={m.id} className="og-run" onClick={() => openMission(m.id)} data-testid="runs-mission-row" data-id={m.id} data-state={m.state}>
          <span className="og-run-dot" data-state={m.state} data-motion={partMotion(m.state === "planned" ? "asked" : m.state === "running" ? "running" : "done")} />
          <span className="mono og-run-id">{m.id}</span>
          <span className="og-run-what">{short(m.goal, 60)}</span>
          <span className="mono muted">{m.state} · {whereLine(m)} · {usd(m.cost_usd)} · {clock(m.created)}</span>
        </button>
      ))}
    </section>
  );
}

/** "Run it across the fleet" (the Start view's goal form, only with more than one harness paired). */
export function AcrossTheFleet() {
  const many = useFleet((s) => s.harnesses.length > 1);
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
