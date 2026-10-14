// Report: the run's checks with ticks and crosses, the finished branch and
// its sha, the tests, the cost; one green sweep (done) when the report
// lands; Copy puts the report text on the clipboard.
import type { MotionState } from "../../lib/motion";
import { Button } from "../../lib/ui";
import { toast } from "../../lib/store";
import { Metric, NoRun } from "./bits";
import { CHECK_LABEL, cost, elapsed, reportText, sha } from "./format";
import { runMotion, useOrch } from "./store";
import type { Check, Report as ReportT } from "./types";

function mark(ok: boolean | null): string {
  return ok === true ? "✓" : ok === false ? "✗" : "—";
}

function copy(r: ReportT): void {
  const text = reportText(r);
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
      <span className="og-check-mark" aria-label={c.ok === true ? "pass" : c.ok === false ? "fail" : "note"}>
        {mark(c.ok)}
      </span>
      <span className="og-check-text">
        <span className="og-check-label">{CHECK_LABEL[c.id] || c.id}</span>
        <span className="og-check-detail mono">{c.detail}</span>
      </span>
    </li>
  );
}

function Pending() {
  const data = useOrch((s) => s.data);
  if (!data) return <NoRun what="The report" />;
  if (data.dry_run)
    return (
      <div className="og-wait">
        <div className="glance-kicker mono">DRY RUN</div>
        {data.dry_run.stop ? (
          <p>The lead would stop: {data.dry_run.stop}</p>
        ) : data.dry_run.problems.length ? (
          <p>The split does not pass the check: {data.dry_run.problems.join("; ")}</p>
        ) : (
          <ol className="og-dry mono">
            {data.dry_run.jobs.map((j) => (
              <li key={j.id}>
                worker {j.worker} · {j.title} <span className="muted">{j.claims.join(", ")}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    );
  return <div className="og-wait muted">The report lands when the run ends{data.live ? " (it is running)" : ""}.</div>;
}

export function ReportDetail() {
  const r = useOrch((s) => s.data?.report);
  if (!r) return <Pending />;
  const passed = r.checks.filter((c) => c.ok === true).length;
  const judged = r.checks.filter((c) => c.ok !== null).length;
  return (
    <div className="og-report">
      <div className="og-report-head">
        <span className="og-badge mono" data-state={r.status}>
          {r.status.toUpperCase()}
        </span>
        <span className="mono">
          {passed}/{judged} checks
        </span>
        <Button size="sm" onClick={() => copy(r)}>
          Copy
        </Button>
      </div>
      {r.stop_reason && <p className="og-stop">{r.stop_reason}</p>}
      <dl className="og-facts mono">
        <dt>branch</dt>
        <dd>{r.branch}</dd>
        <dt>sha</dt>
        <dd>{sha(r.finished)}</dd>
        <dt>tests</dt>
        <dd data-ok={String(r.tests_ok)}>{r.tests_ok ? "pass" : "do not pass"}</dd>
        <dt>cost</dt>
        <dd>{cost(r.cost_usd)}</dd>
        <dt>time</dt>
        <dd>{elapsed(r.elapsed_s)}</dd>
      </dl>
      <ul className="og-checks">
        {r.checks.map((c) => (
          <CheckRow key={c.id} c={c} />
        ))}
      </ul>
    </div>
  );
}

export function ReportGlance() {
  const r = useOrch((s) => s.data?.report);
  if (!r) return <Pending />;
  const judged = r.checks.filter((c) => c.ok !== null);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={`${judged.filter((c) => c.ok).length}/${judged.length}`} label="checks pass" tone={judged.every((c) => c.ok) ? "ok" : "bad"} />
        <Metric value={cost(r.cost_usd)} label="cost" />
      </div>
      <div className="og-pips" aria-hidden="true">
        {judged.map((c) => (
          <span key={c.id} className="og-pip" data-ok={String(c.ok)} title={CHECK_LABEL[c.id] || c.id} />
        ))}
      </div>
      <div className="glance-hint mono">
        {r.status} · {r.branch} {sha(r.finished)}
      </div>
    </div>
  );
}

export function ReportSettings() {
  const r = useOrch((s) => s.data?.report);
  return r ? (
    <Button size="sm" onClick={() => copy(r)}>
      Copy the report text
    </Button>
  ) : (
    <p className="muted">No report yet.</p>
  );
}

export function useReportMotion(): MotionState {
  const status = useOrch((s) => s.data?.report?.status);
  const doneAt = useOrch((s) => s.doneAt);
  return status ? runMotion(status, doneAt) : "none";
}
