// The Mission panel's Plan face (3.0.6.0 R8): the lead's plan as a table,
// one row per part (its number, title and kind, the harness with the reason
// on hover and a lock when it was pinned by capability, what it needs, the
// files it claims, what it waits for, the estimate) and Drop; 3.2.0.0 R4: a
// need a pack capability meets names its pack and harness, and the selected
// part's pack inspector lines show under the table (PackCaps.tsx). The same plan
// is drawn over the Fleet map (MapMission.tsx): drag a part's node to
// another harness box to move it. Plan again asks the lead again; Approve
// and Run (Run approves first) list what still stops them.
import { Button, Icon } from "../../lib/ui";
import { short } from "../orchestra/format";
import { EDITABLE, missions, partState, useMissions, usd, type PlanPart, type View } from "./mstore";
import { approve, dropPart, planAgain, runIt } from "./mload";
import { PackNeeds, PartPackInspector } from "./PackCaps";

/** What stops an approval (fleet/mission_plan_check.ready, in the browser). */
export function readyProblems(v: View | null): string[] {
  const parts = v?.plan?.parts || [];
  if (!parts.length) return ["the mission has no plan yet"];
  return [
    ...parts.filter((p) => p.unassignable).map((p) => `part ${p.id} is unassignable: ${p.unassignable}`),
    ...parts.filter((p) => !p.harness && !p.unassignable).map((p) => `part ${p.id} has no harness`),
  ];
}

/** The pinned lock: a part that needs what only this harness has. */
export function Lock({ title }: { title: string }) {
  return (
    <svg className="fmi-lock" data-testid="fleet-mission-lock" width="10" height="12" viewBox="0 0 10 12" role="img" aria-label="pinned by capability">
      <title>{title}</title>
      <rect x="1" y="5" width="8" height="6" rx="1.2" />
      <path d="M3 5V3.6a2 2 0 0 1 4 0V5" />
    </svg>
  );
}

function Harness({ p }: { p: PlanPart }) {
  if (p.unassignable) return <span className="og-chip mono fmi-bad" data-testid="fleet-mission-unassignable" title={p.unassignable}>unassignable</span>;
  return (
    <span className="fmi-harness" title={p.reason || "no reason given"}>
      {p.pinned && <Lock title={`pinned: ${p.reason}`} />}
      {p.harness_name || "no harness"}
    </span>
  );
}

function Waits({ p }: { p: PlanPart }) {
  const seq = new Map((p.sequenced || []).map((x) => [x.after, x.because]));
  if (!p.depends_on.length) return <span className="muted">-</span>;
  return (
    <>
      {p.depends_on.map((d) => (
        <span key={d} className="og-chip mono fmi-dep" data-seq={seq.has(d) || undefined} title={seq.get(d) || `part ${p.id} starts after part ${d} is done`}>
          {seq.has(d) ? `after ${d} (claims)` : d}
        </span>
      ))}
    </>
  );
}

function PartRow({ p, v, sel, editable }: { p: PlanPart; v: View; sel: boolean; editable: boolean }) {
  const st = partState(v, p.id);
  return (
    <tr className="fmi-prow" data-testid="fleet-mission-part-row" data-part={p.id} data-harness={p.harness || ""} aria-selected={sel}
        onClick={() => missions.update(() => ({ selPart: p.id }))}>
      <td className="mono fmi-pid">{p.id}</td>
      <td className="fmi-ptitle">
        <b title={p.brief}>{short(p.title, 60)}</b> <span className="og-chip mono" data-kind={p.kind}>{p.kind}</span>
        {st !== "planned" && <span className="fmi-pstate mono" data-state={st}>{st}</span>}
      </td>
      <td><Harness p={p} /></td>
      <td className="mono fmi-small"><PackNeeds p={p} /></td>
      <td className="mono fmi-small" title={p.claims.join("\n")}>{short(p.claims.join(", "), 22) || "-"}</td>
      <td><Waits p={p} /></td>
      <td className="mono">{usd(p.est_cost_usd)}</td>
      <td>{editable && <Button size="sm" variant="ghost" onClick={(e) => (e.stopPropagation(), void dropPart(p.id))} data-testid="fleet-mission-drop" title="take this part out of the plan">Drop</Button>}</td>
    </tr>
  );
}

export function MissionPlan() {
  const v = useMissions((s) => s.view);
  const sel = useMissions((s) => s.selPart);
  const busy = useMissions((s) => s.busy);
  const problems = useMissions((s) => s.problems);
  if (!v?.plan) {
    return (
      <div className="fmi-plan" data-testid="fleet-mission-plan">
        <p className="muted">{v?.mission.plan_problems?.length ? "The lead's plan did not pass the check:" : "No plan yet."}</p>
        {v?.mission.plan_problems && <ul className="og-problems">{v.mission.plan_problems.map((p) => <li key={p}>{p}</li>)}</ul>}
        <Button variant="primary" disabled={!!busy} onClick={() => void planAgain()} data-testid="fleet-mission-replan">{busy === "plan" ? "The lead is splitting it..." : "Plan again"}</Button>
      </div>
    );
  }
  const state = v.mission.state;
  const editable = EDITABLE.includes(state);
  const blocked = readyProblems(v);
  const seq = v.plan.parts.flatMap((p) => (p.sequenced || []).map((x) => x.because));
  const est = v.plan.parts.reduce((n, p) => n + (Number(p.est_cost_usd) || 0), 0);
  return (
    <div className="fmi-plan" data-testid="fleet-mission-plan">
      <div className="fmi-plan-head mono muted">
        {v.plan.parts.length} parts on {new Set(v.plan.parts.map((p) => p.harness_name).filter(Boolean)).size} harnesses · est {usd(est)}
        {v.mission.budget_usd ? ` of ${usd(v.mission.budget_usd)}` : ""} · lead {usd(v.plan.lead_cost_usd)}
        {editable && <span className="fmi-drag-hint"> · drag a part on the map to another harness to move it</span>}
      </div>
      <div className="fmi-table-wrap">
        <table className="fmi-table" data-testid="fleet-mission-table">
          <thead><tr><th>#</th><th>part</th><th>harness</th><th>needs</th><th>claims</th><th>waits for</th><th>est</th><th /></tr></thead>
          <tbody>{v.plan.parts.map((p) => <PartRow key={p.id} p={p} v={v} sel={sel === p.id} editable={editable} />)}</tbody>
        </table>
      </div>
      <PartPackInspector p={v.plan.parts.find((x) => x.id === sel)} />
      {(seq.length > 0 || v.plan.notes.length > 0) && (
        <ul className="fmi-notes">
          {[...new Set([...seq, ...v.plan.notes])].map((n) => <li key={n} className={seq.includes(n) ? "fmi-seq-note" : "muted"}>{n}</li>)}
        </ul>
      )}
      {v.plan.merge_order.length > 0 && <div className="mono muted fmi-small">merge order: {v.plan.merge_order.join(" -> ")}</div>}
      {editable && (
        <div className="fmi-actions">
          <Button variant="ghost" icon={<Icon name="reset" />} disabled={!!busy} onClick={() => void planAgain()} data-testid="fleet-mission-replan">{busy === "plan" ? "Planning..." : "Plan again"}</Button>
          {state === "planned" && <Button disabled={!!busy || blocked.length > 0} onClick={() => void approve()} data-testid="fleet-mission-approve">Approve</Button>}
          <Button variant="primary" icon={<Icon name="play" />} disabled={!!busy || blocked.length > 0} onClick={() => void runIt()} data-testid="fleet-mission-run"
                  title={state === "planned" ? "approves the plan, then starts the parts" : "starts the parts by their dependencies"}>
            {busy === "run" ? "Starting..." : "Run"}
          </Button>
          {state === "approved" && <span className="muted fmi-hint">approved by {v.mission.approved_by || "you"}</span>}
        </div>
      )}
      {editable && blocked.length > 0 && (
        <div className="fmi-blocked" data-testid="fleet-mission-blocked">
          <b>Not ready to approve:</b>
          <ul>{blocked.map((p) => <li key={p}>{p}</li>)}</ul>
          <span className="muted">Drop the part, drag it to a harness that has what it needs, or plan again.</span>
        </div>
      )}
      {problems.length > 0 && <ul className="og-problems fmi-problems" data-testid="fleet-mission-problems">{problems.map((p) => <li key={p}>{p}</li>)}</ul>}
    </div>
  );
}
