// The plan editor's toolbar and problem list (3.0.9.0 R2): the run, how many
// lanes (and how many the lead planned), whether the draft is being checked,
// Add lane, Undo / Redo, Reject (a card asks for the reason), and Approve and
// run, which stays disabled while a problem remains and names them. Under
// it every problem (data-testid plan-problem: click one to select its card)
// and the lineup's preflight findings.
import { useState } from "react";
import { Button } from "../../../lib/ui";
import { addLane, approve, redo, reject, undo } from "./actions";
import { plan, selectLane, usePlan } from "./store";

export function PlanBar() {
  const runId = usePlan((s) => s.runId);
  const n = usePlan((s) => s.jobs.length);
  const lead = usePlan((s) => s.leadCount);
  const problems = usePlan((s) => s.problems);
  const saving = usePlan((s) => s.saving);
  const busy = usePlan((s) => s.busy);
  const canUndo = usePlan((s) => s.past.length > 0);
  const canRedo = usePlan((s) => s.future.length > 0);
  const blocked = problems.length > 0 || saving;
  const why = problems.length
    ? `Fix ${problems.length} problem${problems.length === 1 ? "" : "s"} first: ${problems.map((p) => p.text).join(" · ")}`
    : saving ? "Checking the edit..." : "Run these lanes now";
  return (
    <div className="rc-bar pc-bar">
      <b className="rc-bar-name mono">run {runId}</b>
      <span className="og-badge mono" data-state="planned">PLANNED</span>
      <span className="mono muted rc-bar-count">{n} lane{n === 1 ? "" : "s"} · the lead planned {lead}</span>
      {saving && <span className="rc-dirty mono" data-testid="plan-saving">checking</span>}
      <span className="spacer" />
      <Button size="sm" onClick={addLane} data-testid="plan-add">Add lane</Button>
      <Button size="sm" variant="ghost" disabled={!canUndo} onClick={undo} title="Undo the last edit (Ctrl+Z)" data-testid="plan-undo">Undo</Button>
      <Button size="sm" variant="ghost" disabled={!canRedo} onClick={redo} title="Redo (Ctrl+Shift+Z)" data-testid="plan-redo">Redo</Button>
      <Button size="sm" variant="danger" disabled={!!busy} onClick={() => plan.update((s) => ({ rejecting: !s.rejecting }))} data-testid="plan-reject">Reject</Button>
      <Button size="sm" variant="primary" disabled={blocked || !!busy} onClick={() => void approve()} title={why} data-testid="plan-approve"
              data-blocked={problems.length || undefined}>
        {busy === "approve" ? "Approving..." : "Approve and run"}
      </Button>
    </div>
  );
}

export function RejectCard() {
  const open = usePlan((s) => s.rejecting);
  const busy = usePlan((s) => s.busy);
  const [reason, setReason] = useState("");
  if (!open) return null;
  return (
    <div className="pc-reject" data-testid="plan-reject-card" role="group" aria-label="Reject the plan">
      <b>Reject the plan</b>
      <span className="muted">The run stops with this reason; the report shows it.</span>
      <textarea className="input" rows={2} value={reason} placeholder="e.g. one lane per file instead" onChange={(e) => setReason(e.target.value)}
                data-testid="plan-reject-reason" autoFocus />
      <div className="og-actions">
        <Button size="sm" variant="danger" disabled={!reason.trim() || !!busy} onClick={() => void reject(reason.trim())} data-testid="plan-reject-confirm">
          Reject and stop the run
        </Button>
        <Button size="sm" variant="ghost" onClick={() => plan.update(() => ({ rejecting: false }))}>Keep editing</Button>
      </div>
    </div>
  );
}

export function PlanProblems() {
  const problems = usePlan((s) => s.problems);
  const preflight = usePlan((s) => s.preflight);
  const error = usePlan((s) => s.error);
  if (!problems.length && !preflight.length && !error)
    return <p className="pc-ok mono" data-testid="plan-ok">No problems: Approve and run starts these lanes.</p>;
  return (
    <div className="pc-problems">
      {error && <p className="og-problems">{error}</p>}
      {problems.length > 0 && (
        <ul className="og-problems" role="alert" aria-label="What stops this plan">
          {problems.map((p, i) => (
            <li key={i} data-testid="plan-problem" data-jobs={p.jobs.join(" ")}>
              <button type="button" className="og-link" onClick={() => p.jobs[0] && selectLane(p.jobs[0])}>{p.text}</button>
            </li>
          ))}
        </ul>
      )}
      {preflight.length > 0 && (
        <ul className="pc-preflight" aria-label="The lineup's preflight">
          {preflight.map((f) => (
            <li key={f.id} data-severity={f.severity} title={f.fix}>lineup: {f.text}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
