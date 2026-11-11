// A run's lane (and its lead) and a mission part on Live, as hover cards (3.3.16.1): what it owns, its state, its machine,
// its worker and model, what it waits for, its cost. A lane's click opens Runs focused on that lane (it has no inspector
// page of its own); the lead's opens Runs on the run; a part's click puts its card in the inspector.
import { LANE_LABEL, useOrch } from "../../orchestra/store";
import { ownsOf } from "../run/Owns";
import { partAgent } from "../../fleet/MissionRun";
import { partState, useMissions } from "../../fleet/mstore";
import { useFleet } from "../../fleet/store";
import { HoverBody, type HoverRow } from "../../../lib/hover/HoverBody";
import { joined, plural, spent } from "./words";

const NO_JOBS: string[] = [];

export function LaneHover({ run, lane }: { run: string; lane: number | undefined }) {
  const data = useOrch((s) => (s.data?.run.run_id === run ? s.data : null));
  if (!data) return null;
  const goal = data.goal;
  if (!lane) {
    const rows: HoverRow[] = [
      ["Run", run],
      ["State", data.live ? "running" : "ended"],
      ["Lanes", plural(data.lanes.length, "lane")],
      ["Lead model", goal.lead || "the lead role's model"],
      ["Worker model", goal.worker || "the worker role's model"],
      ["Cost", spent(data.run.cost_usd)],
      ["Done when", goal.done_when],
    ];
    return <HoverBody title="lead" is={goal.what} rows={rows} foot="Click: the run in Agents -> Runs" />;
  }
  const l = data.lanes.find((x) => x.lane === lane);
  if (!l) return null;
  const owns = ownsOf(l, data.claims || []);
  const after = l.after || NO_JOBS;
  const rows: HoverRow[] = [
    ["Owns", owns.join(", ") || "nothing yet"],
    ["State", joined([LANE_LABEL[l.state] || l.state, l.error], ": ")],
    ["Machine", "this halo"],
    ["Worker", l.holder || "not joined yet"],
    ["Model", goal.worker || "the worker role's model"],
    ["Worktree", l.branch],
    ["Waits for", after.length ? after.join(", ") : ""],
    ["Cost", spent(l.cost_usd)],
  ];
  return <HoverBody title={`lane ${l.lane}`} is={l.title || owns.join(", ")} rows={rows} foot="Click: this lane in Agents -> Runs" />;
}

export function PartHover({ pid }: { pid: string }) {
  const v = useMissions((s) => s.view);
  const harnesses = useFleet((s) => s.harnesses);
  const p = v?.plan?.parts.find((x) => x.id === pid);
  if (!v || !p) return null;
  const st = partState(v, pid);
  const run = v.mission.parts?.[pid];
  const live = st === "running" ? partAgent(harnesses, v.mission.id, pid, run?.harness || p.harness) : null;
  const rows: HoverRow[] = [
    ["Owns", p.claims.join(", ") || "nothing named"],
    ["State", st],
    ["Machine", joined([run?.harness_name || p.harness_name || "nobody can run it yet", p.pinned && "pinned"])],
    ["Worker", live ? joined([String(live.agent.name || live.agent.agent_id), live.agent.model]) : ""],
    ["Waits for", p.depends_on.length ? p.depends_on.map((d) => `part ${d}`).join(", ") : ""],
    ["Kind", p.kind === "repo" ? "repo: works in a checkout" : "files: hands files on"],
    ["Cost", run?.cost_usd ? spent(run.cost_usd) : p.est_cost_usd ? `about ${spent(p.est_cost_usd)} (estimate)` : ""],
    ["Why here", p.unassignable || p.reason],
  ];
  return <HoverBody title={`part ${p.id}: ${p.title}`} is={p.brief} rows={rows} foot="Click: its card in the inspector" />;
}
