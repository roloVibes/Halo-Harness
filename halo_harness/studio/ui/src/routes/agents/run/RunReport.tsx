// A finished goal run's report, as a page of History (3.4.0.0 D "the runs fold"; Runs' Report panel before): how it
// ended and why, the goal, the facts (branch, sha, tests, cost, time, models), the plan and its lanes (what each owned,
// how it ended, how often the gate sent it back, its model and cost), the gate (DONE WHEN, the test and its tail), the
// merge (the order, what merged, the conflicts), the outcome checks, a workflow run's artifacts; a dry run shows the
// lead's jobs. Copy puts the text `halo orchestra report` prints on the clipboard; Replay draws it on Live as it ended;
// Run it again opens the goal panel with this goal filled in.
import type { ReactNode } from "react";
import { Button } from "../../../lib/ui";
import { toast } from "../../../lib/store";
import { StateBadge } from "../../orchestra/bits";
import { ArtifactsTab } from "../../orchestra/Artifacts";
import { CHECK_LABEL, cost, elapsed, reportText, sha, short } from "../../orchestra/format";
import type { Check, RunPayload } from "../../orchestra/types";
import { openLiveReplay } from "../live/replay";
import { closeReport, toggleHistory } from "../live/historyStore";
import { openGoal } from "./goalStore";

const mark = (ok: boolean | null) => (ok === true ? "✓" : ok === false ? "✗" : "—");

function copy(text: string): void {
  const done = () => toast("Report copied", "done");
  try {
    navigator.clipboard.writeText(text).then(done, () => toast("The clipboard is closed to this page: select the text instead", "error"));
  } catch {
    toast("The clipboard is closed to this page", "error");
  }
}

function CheckRow({ c }: { c: Check }) {
  return (
    <li className="og-check" data-ok={c.ok === null ? "info" : String(c.ok)} data-testid="report-check">
      <span className="og-check-mark" aria-label={c.ok === true ? "pass" : c.ok === false ? "fail" : "note"}>{mark(c.ok)}</span>
      <span className="og-check-text">
        <span className="og-check-label">{CHECK_LABEL[c.id] || c.id}</span>
        <span className="og-check-detail mono" title={c.detail}>{c.detail}</span>
      </span>
    </li>
  );
}

function Block({ title, testid, children }: { title: string; testid: string; children: ReactNode }) {
  return (
    <section className="rr-block" data-testid={testid}>
      <div className="rail-label mono">{title}</div>
      {children}
    </section>
  );
}

function Lanes({ data }: { data: RunPayload }) {
  const byLane = new Map((data.report?.lanes || []).map((l) => [l.lane, l]));
  if (!data.lanes.length) return <p className="muted">No lane joined: the run ended before the split ({data.run.state}).</p>;
  return (
    <ul className="rr-lanes mono">
      {data.lanes.map((l) => {
        const r = byLane.get(l.lane);
        const facts = [r?.state || l.state || "pending", l.pieces_returned ? `sent back ${l.pieces_returned}x` : "", l.model || "", cost(r?.cost_usd ?? l.cost_usd)];
        return (
          <li key={l.lane} className="rr-lane" data-testid="report-lane" data-lane={l.lane} data-state={r?.state || l.state}>
            <span className="og-lane-n" data-lc={String((l.lane - 1) % 10)}>{l.lane}</span>
            <span className="rr-lane-what" title={l.title}>{short(l.title, 80) || l.job}</span>
            <span className="muted rr-lane-owns" title={l.claims.join(", ")}>owns {short(l.claims.join(", "), 60) || "nothing named"}</span>
            <span className="rr-lane-facts">{facts.filter(Boolean).join(" · ")}</span>
            {l.error && <span className="rr-lane-err">{l.error}</span>}
          </li>
        );
      })}
    </ul>
  );
}

export function RunReport({ data }: { data: RunPayload }) {
  const r = data.report;
  const run = data.run.run_id;
  const models = [...new Set(data.lanes.map((l) => l.model || "").filter(Boolean))];
  const judged = (r?.checks || []).filter((c) => c.ok !== null);
  const again = () => openGoal({ ...data.goal, files: [...(data.goal.files || [])], model: "", review: data.goal.plan === "review" });
  return (
    <div className="rr" data-testid="history-report" data-run={run} data-state={data.run.state}>
      <div className="rr-head" data-density="bar">
        <Button size="sm" variant="ghost" onClick={closeReport} data-testid="history-report-back" title="Back to History's list">Back</Button>
        <StateBadge state={data.run.state} />
        {r && <span className="mono">{judged.filter((c) => c.ok).length}/{judged.length} checks</span>}
        <span className="spacer" />
        {r && <Button size="sm" variant="ghost" onClick={() => copy(reportText(r))} data-testid="history-report-copy" title="The report as halo orchestra report prints it">Copy</Button>}
        <Button size="sm" variant="ghost" data-testid="history-report-replay" title="Draw it on Live as it ended (Back to now returns)"
                onClick={() => void openLiveReplay("run", run, data.goal.what).then((ok) => ok && toggleHistory(false))}>Replay</Button>
        <Button size="sm" onClick={again} data-testid="history-report-again" title="The goal panel with this goal filled in: nothing runs until you press Run">Run it again</Button>
      </div>
      <h3 className="rr-goal">{data.goal.what}</h3>
      {r?.stop_reason && <p className="og-stop" data-testid="history-report-stop">{r.stop_reason}</p>}
      <dl className="og-facts mono">
        <dt>run</dt><dd>{run}</dd>
        {r && <><dt>branch</dt><dd title={r.branch}>{r.branch} {sha(r.finished)}</dd></>}
        {r && <><dt>tests</dt><dd data-ok={String(r.tests_ok)}>{r.tests_ok ? "pass" : "do not pass"}</dd></>}
        <dt>cost</dt><dd>{cost(r?.cost_usd ?? data.run.cost_usd)}</dd>
        {r && <><dt>time</dt><dd>{elapsed(r.elapsed_s)}</dd></>}
        <dt>models</dt><dd>{models.join(", ") || "the roles' (none recorded)"}</dd>
      </dl>
      {data.dry_run && (
        <Block title="DRY RUN · THE LEAD'S JOBS" testid="history-report-dry">
          {data.dry_run.stop ? <p>The lead would stop: {data.dry_run.stop}</p>
            : data.dry_run.problems.length ? <p>The split does not pass the check: {data.dry_run.problems.join("; ")}</p>
            : <ol className="og-dry mono">{data.dry_run.jobs.map((j) => <li key={j.id}>worker {j.worker} · {j.title} <span className="muted">{j.claims.join(", ")}</span></li>)}</ol>}
        </Block>
      )}
      <Block title={`THE PLAN AND ITS LANES · ${data.lanes.length}`} testid="history-report-lanes"><Lanes data={data} /></Block>
      <Block title="THE GATE" testid="history-report-gate">
        <p className="mono muted">done when: {data.goal.done_when || "not said"} · test: {data.goal.test || "none"} · sends a part back up to {data.goal.return_cap}x</p>
        {r?.tests_tail && <pre className="rr-tail mono">{r.tests_tail}</pre>}
      </Block>
      {data.merge && (
        <Block title="THE MERGE" testid="history-report-merge">
          <p className="mono">{data.merge.branch} from {sha(data.merge.base)} · merged {data.merge.merged.join(", ") || "none"} of {data.merge.order.join(", ") || "none"}
            {data.merge.conflicts.length ? ` · ${data.merge.conflicts.length} conflict${data.merge.conflicts.length === 1 ? "" : "s"} judged` : ""}</p>
        </Block>
      )}
      {r && <Block title="OUTCOMES" testid="history-report-checks"><ul className="og-checks">{r.checks.map((c) => <CheckRow key={c.id} c={c} />)}</ul></Block>}
      {!!r?.artifacts?.length && <Block title="ARTIFACTS" testid="history-report-artifacts"><ArtifactsTab runId={run} rows={r.artifacts} ref={r.workflow?.ref} /></Block>}
      {!r && !data.dry_run && <p className="muted">No report: the run ended without one ({data.run.state}).</p>}
    </div>
  );
}
