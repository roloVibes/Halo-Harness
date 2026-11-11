// A mission part in Agents -> Live's inspector (3.3.16.0 R2 "the Fleet fold"): its card, summary first -- the part, its
// state and the machine it runs on (and why there), what it was asked, what it needs, what it waits for, what it owns
// (its claims: the owns line R1 added to a run's lanes), what it hands on, the cost so far or the estimate, its agent
// while it runs (a click puts the agent in the inspector), its packs' inspector lines; "Open in Runs" opens the mission
// there on this part, one click.
import { Button } from "../../../lib/ui";
import { short } from "../../orchestra/format";
import { openMission } from "../../fleet/mload";
import { partAgent } from "../../fleet/MissionRun";
import { partState, useMissions, usd } from "../../fleet/mstore";
import { PartPackInspector } from "../../fleet/PackCaps";
import { useFleet } from "../../fleet/store";
import { OwnsLine } from "../run/Owns";
import { selectLive } from "../../roles/liveModel";

export function PartCard({ id }: { id: string }) {
  const v = useMissions((s) => s.view);
  const harnesses = useFleet((s) => s.harnesses);
  const p = v?.plan?.parts.find((x) => x.id === id);
  if (!v || !p) return <p className="muted" data-testid="live-part-gone">That part is not in the open mission any more.</p>;
  const st = partState(v, p.id);
  const run = v.mission.parts?.[p.id];
  const live = partAgent(harnesses, v.mission.id, p.id, run?.harness || p.harness);
  const lines: [string, string][] = [
    ["state", `${st}${run?.waiting ? ` · ${run.waiting}` : ""}`],
    ["runs on", `${run?.harness_name || p.harness_name || "no machine yet"}${p.reason ? ` -- ${p.reason}` : ""}`],
    ["asked", p.brief || p.title],
    ["needs", p.needs.join(", ") || "nothing special"],
    ["after", p.depends_on.length ? p.depends_on.map((d) => `part ${d}`).join(", ") : "starts first"],
    ["cost", run?.cost_usd ? usd(run.cost_usd) : `est ${usd(p.est_cost_usd)}`],
  ];
  return (
    <div className="ri-sum lv-part" data-testid="live-part" data-part={p.id} data-mission={v.mission.id} data-state={st}>
      <header className="fa-head">
        <div className="fa-head-row">
          <span className="og-chip mono">part {p.id}</span>
          <b className="fa-name">{short(p.title, 48)}</b>
          <span className="spacer" />
          <span className="og-chip mono">{p.kind}</span>
        </div>
        <div className="fa-meta mono muted">mission {v.mission.id} · {short(v.mission.goal, 60)}</div>
      </header>
      <dl className="ri-summary">
        {lines.map(([k, text]) => (
          <div key={k} data-line={k}>
            <dt className="mono">{k}</dt>
            <dd>{text}</dd>
          </div>
        ))}
      </dl>
      <OwnsLine keys={p.claims} testid="live-part-owns" />
      {p.unassignable && <p className="og-problems">{p.unassignable}</p>}
      <div className="og-actions">
        <Button size="sm" variant="primary" onClick={() => openMission(v.mission.id, p.id)} data-testid="live-part-open">Open in Runs</Button>
        {live && <Button size="sm" variant="ghost" onClick={() => selectLive(live.key)} data-testid="live-part-agent">Its agent</Button>}
      </div>
      <PartPackInspector p={p} />
    </div>
  );
}
