// The Mission panel's Report face (3.0.6.0 R8): `GET .../report` (R7's
// report.json): who did what on which harness, the cost per harness and per
// part against the estimate and the budget, the decisions and who made
// them, the files, the edits refused outside a part's claims, what failed,
// the merge, and the artifacts with Open (a text file opens in the viewer,
// a binary says its size).
import { Button, Empty } from "../../lib/ui";
import { elapsed, short } from "../orchestra/format";
import { age } from "./pstore";
import { useMissions, usd } from "./mstore";
import { openFile } from "./mload";

function sizeOf(n: number | undefined): string {
  if (n === undefined) return "";
  return n < 1024 ? `${n} B` : n < 1048576 ? `${Math.round(n / 1024)} KB` : `${(n / 1048576).toFixed(1)} MB`;
}

export function MissionReport() {
  const r = useMissions((s) => s.report);
  const error = useMissions((s) => s.reportError);
  const files = useMissions((s) => s.files);
  if (!r) return error ? <Empty title="Studio could not read the report" body={error} /> : <div className="og-wait mono muted">reading the report...</div>;
  const rep = r.report;
  const c = rep.cost;
  const sizes = new Map((files || []).map((f) => [f.path, f.size]));
  const hand = (files || []).filter((f) => /^parts\/\d+\/handback\.md$/.test(f.path)).map((f) => f.path);
  return (
    <div className="fmi-report" data-testid="fleet-mission-report">
      <div className="fmi-report-head">
        <span className="og-chip mono fmi-state" data-state={rep.state}>{rep.state}</span>
        <span className="mono muted">{r.final ? "final" : "so far"} · {rep.duration_s != null ? elapsed(rep.duration_s) : "-"}</span>
        <span className="spacer" />
        <b className="mono" data-testid="fleet-mission-total" title={`plan ${usd(c.plan_usd)} + parts ${usd(c.parts_usd)}; estimate ${usd(c.est_usd)}`}>
          {usd(c.total_usd)}{c.budget_usd ? ` of ${usd(c.budget_usd)}` : ""}
        </b>
        {c.over_budget && <span className="og-chip mono fmi-bad">over budget</span>}
      </div>
      {rep.stop_reason && <p className="muted fmi-small">Stopped: {rep.stop_reason}</p>}
      <div className="rail-label mono">COST PER HARNESS</div>
      <table className="fmi-table fmi-htable" data-testid="fleet-mission-report-harnesses">
        <thead><tr><th>harness</th><th>parts</th><th>done</th><th>failed</th><th>cost</th></tr></thead>
        <tbody>
          {rep.harnesses.map((h) => (
            <tr key={h.harness} data-testid="fleet-mission-report-harness" data-name={h.name}>
              <td>{h.name}</td><td className="mono">{h.parts.join(", ")}</td><td className="mono">{h.done}</td><td className="mono">{h.failed}</td><td className="mono">{usd(h.cost_usd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="rail-label mono">WHO DID WHAT</div>
      <table className="fmi-table">
        <thead><tr><th>#</th><th>part</th><th>harness</th><th>state</th><th>cost / est</th><th>time</th><th>files</th></tr></thead>
        <tbody>
          {rep.parts.map((p) => (
            <tr key={p.id} data-testid="fleet-mission-report-part" data-part={p.id}>
              <td className="mono">{p.id}</td>
              <td title={p.error || ""}>{short(p.title, 48)}{p.error && <div className="muted fmi-small">{short(p.error, 80)}</div>}</td>
              <td>{p.harness_name}</td>
              <td><span className="fmi-pstate mono" data-state={p.merged ? "merged" : p.state}>{p.merged ? "merged" : p.state}</span></td>
              <td className="mono">{usd(p.cost_usd)} / {usd(p.est_cost_usd)}</td>
              <td className="mono">{p.duration_s != null ? elapsed(p.duration_s) : "-"}</td>
              <td className="mono" title={p.files.join("\n")}>{p.files.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rep.decisions.length > 0 && (
        <>
          <div className="rail-label mono">DECISIONS</div>
          <ul className="fmi-notes">{rep.decisions.map((d) => <li key={d.ts + d.what}><span className="mono muted">{age(d.ts)} ago</span> {d.what} <span className="muted">by {d.by || "the hub"}</span></li>)}</ul>
        </>
      )}
      {rep.refused.length > 0 && (
        <>
          <div className="rail-label mono">EDITS REFUSED OUTSIDE A PART'S CLAIMS</div>
          <ul className="fmi-notes">{rep.refused.map((x) => <li key={x.part + x.file + x.ts} className="fmi-seq-note">part {x.part} on {x.harness}: {x.tool} {x.file}</li>)}</ul>
        </>
      )}
      {rep.failed.length > 0 && (
        <>
          <div className="rail-label mono">WHAT FAILED</div>
          <ul className="og-problems">{rep.failed.map((f) => <li key={f.part}>part {f.part} {f.state}: {f.error}</li>)}</ul>
        </>
      )}
      {rep.merge && (
        <p className="mono fmi-small">
          merge {rep.merge.ok ? "ok" : "not finished"}: {rep.merge.merged.join(", ") || "nothing"} into {rep.merge.branch}
          {rep.merge.conflicts.length ? ` · ${rep.merge.conflicts.length} conflict${rep.merge.conflicts.length === 1 ? "" : "s"} judged` : ""}
          {rep.merge.error ? ` · ${rep.merge.error}` : ""}
        </p>
      )}
      <div className="rail-label mono">ARTIFACTS AND HAND-BACKS</div>
      {rep.artifacts.length + hand.length === 0 ? <p className="muted fmi-small">Nothing written to the mission folder yet.</p> : (
        <ul className="fmi-files" data-testid="fleet-mission-artifacts">
          {[...hand, ...rep.artifacts].map((a) => (
            <li key={a}>
              <span className="mono">{a}</span> <span className="muted mono">{sizeOf(sizes.get(a))}</span>
              <Button size="sm" variant="ghost" onClick={() => void openFile(a)} data-testid="fleet-mission-artifact-open">Open</Button>
            </li>
          ))}
        </ul>
      )}
      {rep.missing_outputs.length > 0 && <p className="muted fmi-small">Declared but missing: {rep.missing_outputs.join(", ")}</p>}
    </div>
  );
}
