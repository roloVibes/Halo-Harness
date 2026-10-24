// fleet-mission (3.0.6.0 R8): one goal for the whole fleet. Four faces:
// Start (the goal box and every mission: MissionStart.tsx), Plan (the parts
// as a table, the same plan drawn on the map where a part is dragged to
// another harness: MissionPlan.tsx, MapMission.tsx), Running (parts by state
// live, cost per harness, the merge queue, Stop: MissionRun.tsx) and Report
// (MissionReport.tsx), and once it ended Coach (3.0.9.0 R3: the post-run
// coach's cards, lib/coach). A mission opens on the face its state calls for; the
// tabs switch. Compact face: the running mission's goal and its parts by
// state, else "no mission". Store mstore.ts, loader mload.ts.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import { Button, Icon } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { short } from "../orchestra/format";
import { FINAL, LIVE, missions, useMissions, usd, type Summary } from "./mstore";
import { closeMission, openMission, setFace, shownFace, startMissions } from "./mload";
import { MissionCoach } from "./MissionCoach";
import { MissionPlan } from "./MissionPlan";
import { MissionReport } from "./MissionReport";
import { MissionRun } from "./MissionRun";
import { MissionStart, PartStates } from "./MissionStart";
import { MissionMeta } from "./PackCaps";

const TABS: { id: "plan" | "run" | "report" | "coach"; label: string }[] = [
  { id: "plan", label: "Plan" },
  { id: "run", label: "Running" },
  { id: "report", label: "Report" },
  { id: "coach", label: "Coach" },
];

function Head() {
  const v = useMissions((s) => s.view);
  const face = useMissions(shownFace);
  if (!v) return null;
  const m = v.mission;
  const started = LIVE.includes(m.state) || FINAL.includes(m.state);
  return (
    <header className="fmi-head" data-testid="fleet-mission-head" data-state={m.state}>
      <div className="fmi-head-top">
        <button className="og-link mono fmi-back" onClick={closeMission} data-testid="fleet-mission-back" title="every mission, and a new one">
          <Icon name="close" size={12} /> all missions
        </button>
        <span className="spacer" />
        <div className="segmented fmi-tabs" role="tablist" aria-label="Mission view">
          {TABS.filter((t) => (t.id === "coach" ? FINAL.includes(m.state) : t.id === "plan" || started || (t.id === "report" && m.state !== "drafted"))).map((t) => (
            <button key={t.id} role="tab" aria-selected={face === t.id} className={face === t.id ? "on" : ""} onClick={() => setFace(t.id)} data-testid={`fleet-mission-tab-${t.id}`}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      <div className="fmi-head-main">
        <span className="og-chip mono fmi-state" data-state={m.state} data-testid="fleet-mission-state">{m.state}</span>
        <b className="fmi-goal" title={m.goal}>{short(m.goal, 110)}</b>
      </div>
      <div className="fmi-head-sub mono muted">
        {m.id} · hub {m.hub?.name || "-"}{m.repo ? ` · repo ${m.repo.name}${m.repo.branch ? " · " + m.repo.branch : ""}` : " · no repo"}
        {m.constraints ? ` · ${short(m.constraints, 60)}` : ""}
      </div>
      <MissionMeta />
    </header>
  );
}

export function MissionDetail() {
  useEffect(() => startMissions(), []);
  const face = useMissions(shownFace);
  const open = useMissions((s) => s.open);
  const notHere = useMissions((s) => s.notHere);
  const error = useMissions((s) => s.viewError);
  const loaded = useMissions((s) => !!s.view);
  return (
    <div className="fmi" data-testid="fleet-mission-detail" data-face={face}>
      {!open ? <MissionStart /> : notHere ? (
        <div className="fmi-nothere">
          <p>Mission <b className="mono">{notHere}</b> is not on this harness: another hub planned it. Its part runs here once you allow it; its folder arrives when the part starts.</p>
          <Button onClick={closeMission}>All missions</Button>
        </div>
      ) : (
        <>
          <Head />
          <div className="fmi-body">
            {!loaded ? <div className="og-wait mono muted">{error || "reading the mission..."}</div>
              : face === "run" ? <MissionRun /> : face === "report" ? <MissionReport /> : face === "coach" ? <MissionCoach /> : <MissionPlan />}
          </div>
        </>
      )}
    </div>
  );
}

function pick(list: Summary[] | null): Summary | null {
  return (list || []).find((m) => LIVE.includes(m.state)) || (list || []).find((m) => m.state === "planned" || m.state === "approved") || null;
}

export function MissionGlance() {
  useEffect(() => startMissions(), []);
  const list = useMissions((s) => s.list);
  const m = pick(list);
  if (!m)
    return (
      <div className="glance" data-testid="fleet-mission-glance">
        <div className="glance-numbers"><Metric value={list?.length ?? 0} label="missions" /></div>
        <div className="glance-hint">No mission. Expand to give the fleet one goal.</div>
      </div>
    );
  return (
    <div className="glance fmi-glance" data-testid="fleet-mission-glance" data-state={m.state}>
      <button className="og-link fmi-glance-goal" onClick={() => openMission(m.id)} title="open it">{short(m.goal, 80)}</button>
      <div className="mono fmi-small"><span className="fmi-pstate mono" data-state={m.state}>{m.state}</span> <PartStates counts={m.part_states || {}} /> · {usd(m.cost_usd)}</div>
    </div>
  );
}

export function useMissionMotion(): MotionState {
  const list = useMissions((s) => s.list);
  const busy = useMissions((s) => !!s.busy);
  if (busy || (list || []).some((m) => LIVE.includes(m.state))) return "working";
  if ((list || []).some((m) => m.state === "planned")) return "waiting";
  return list?.length ? "idle" : "none";
}

/** How many missions run now (the status bar's FLEET cell). */
export function useRunningMissions(): number {
  return useMissions((s) => (s.list || []).filter((m) => LIVE.includes(m.state)).length);
}

/** The open mission, else the newest that waits on you or runs (the palette). */
export function currentMission(): Summary | null {
  const s = missions.get();
  return (s.list || []).find((m) => m.id === s.open) || pick(s.list);
}
