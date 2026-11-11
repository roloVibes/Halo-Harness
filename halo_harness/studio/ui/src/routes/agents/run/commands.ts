// The palette's goal-run lines (3.4.0.0 D "the runs fold"; Orchestra's new run / stop run / open run / focus lane before),
// in its Agents group: "Agents: Run a goal" (Live's goal panel), and while a run is live "Agents: stop the run" (one
// confirm, in the run's inspector), "Agents: review the plan" (while it waits on you) and "Agents: lane N" (that lane
// in the inspector); then "History: run <id>" for each finished run of this repo (its report page).
import { orch, isLiveRun } from "../../orchestra/store";
import { startOrchestra } from "../../orchestra/sync";
import { openGoal } from "./goalStore";
import { openRun } from "./door";
import { reviewPlan } from "./planPanel";

export type RunCommand = { id: string; group: string; label: string; hint?: string; run: () => void };

export function runCommands(): RunCommand[] {
  startOrchestra();
  const s = orch.get();
  const g = "Agents";
  const out: RunCommand[] = [
    { id: "run-goal", group: g, label: "Agents: Run a goal", hint: "the goal form beside Live's canvas: what you want, done when, the files, the gate's test", run: () => openGoal() },
  ];
  const live = s.data?.live ? s.data : null;
  if (live) {
    const run = live.run.run_id;
    out.push({ id: "run-stop", group: g, label: "Agents: stop the run", hint: `run ${run}: its summary, where Stop asks once`, run: () => void openRun(run) });
    if (live.run.state === "planned") out.push({ id: "run-review", group: g, label: "Agents: review the plan", hint: `run ${run} waits on you`, run: reviewPlan });
    for (const l of live.lanes)
      out.push({ id: "run-lane-" + l.lane, group: g, label: `Agents: lane ${l.lane}`, hint: `${l.state || "pending"} · ${l.title}`, run: () => void openRun(run, l.lane) });
  }
  for (const r of s.runs.filter((x) => !isLiveRun(x.state)).slice(0, 30))
    out.push({ id: "run-report-" + r.run_id, group: "History", label: `History: run ${r.run_id}`, hint: `${r.state} · ${r.goal_what.slice(0, 40)}`, run: () => void openRun(r.run_id) });
  return out;
}
