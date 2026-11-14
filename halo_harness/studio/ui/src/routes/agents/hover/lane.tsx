// A run's lane (and its lead) on Live, as hover cards (3.3.16.1): what it owns, its state, its machine, its worker and
// model, what it waits for, its cost. A lane's click opens Runs focused on that lane (it has no inspector page of its
// own); the lead's opens Runs on the run.
import { LANE_LABEL, useOrch } from "../../orchestra/store";
import { ownsOf } from "../run/Owns";
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
    return <HoverBody title="lead" is={goal.what} rows={rows} foot="Click: the run in Live's inspector" />;
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
  return <HoverBody title={`lane ${l.lane}`} is={l.title || owns.join(", ")} rows={rows} foot="Click: this lane in Live's inspector" />;
}
