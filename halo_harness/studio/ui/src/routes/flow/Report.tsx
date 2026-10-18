// flow-report: the run's report.json -- the status, the cost against the
// budget, the steps table, the artboards, the posts and the metrics summary;
// Copy puts the text `halo flow report` prints on the clipboard. Before the
// report lands it shows the live cost against the budget. 3.0.9.0 R3: once
// the report lands, a Coach tab (lib/coach) beside it.
import { useState } from "react";
import { CoachCards } from "../../lib/coach/CoachCards";
import type { MotionState } from "../../lib/motion";
import { toast } from "../../lib/store";
import { Button } from "../../lib/ui";
import { ReportTabs, type ReportTab } from "../orchestra/Coach";
import { applySuggestion } from "../orchestra/coachApply";
import { cost, elapsed } from "../orchestra/format";
import { CostBar, FlowBadge, Metric, NoFlow } from "./bits";
import { runMotion, stepCount, useFlow } from "./store";
import type { Report } from "./types";

const money = (v: unknown) => `$${(Number(v) || 0).toFixed(4)}`;

/** The report as text, line for line what flows/report.py `format_report` prints. */
export function reportText(r: Report): string {
  const lines = [`flow ${r.name} run ${r.run}: ${r.status}${r.stop_reason ? ` -- ${r.stop_reason}` : ""}`];
  for (const s of r.steps || []) {
    const el = s.elapsed_s;
    const extra = (s.rounds || 0) > 1 ? `  rounds ${s.rounds}` : "";
    lines.push(`  ${String(s.id).padEnd(12)} ${String(s.kind).padEnd(8)} ${String(s.state).padEnd(8)} ${money(s.cost_usd)}  ${(el !== undefined && el !== null ? `${el.toFixed(1)}s` : "-").padStart(8)}${extra}${s.error ? `  error: ${s.error}` : ""}`);
  }
  for (const a of r.artboards || []) lines.push(`  artboard ${a.id} (${a.kind}): ${a.path}`);
  for (const p of r.posts || []) {
    const what = p.dry_run ? "dry run" : p.error ? `failed: ${p.error}` : `live, post ${p.post_id}${p.scheduled_at ? ` scheduled ${p.scheduled_at}` : ""}`;
    lines.push(`  post ${p.platform}: ${what}, ${p.chars} chars, ${p.media} media`);
  }
  if (r.metrics?.summary) lines.push(`  metrics: ${r.metrics.summary}`);
  const b = r.budget_usd;
  lines.push(`  total ${money(r.cost_usd)}${b !== undefined && b !== null ? ` of $${Number(b).toFixed(2)}` : ""} in ${(Number(r.elapsed_s) || 0).toFixed(1)}s; project ${r.project_path || r.project}`);
  return lines.join("\n");
}

function copy(r: Report): void {
  try {
    navigator.clipboard.writeText(reportText(r)).then(
      () => toast("Report copied", "done"),
      () => toast("The clipboard is closed to this page: select the text instead", "error"),
    );
  } catch {
    toast("The clipboard is closed to this page", "error");
  }
}

function Pending() {
  const data = useFlow((s) => s.data);
  if (!data) return <NoFlow what="The report" />;
  return (
    <div className="glance">
      <div className="glance-row">
        <FlowBadge />
        <span className="spacer" />
        <span className="mono">{cost(data.flow.cost_usd)}{data.flow.budget_usd ? <span className="muted"> of {cost(data.flow.budget_usd)}</span> : null}</span>
      </div>
      <CostBar spent={data.flow.cost_usd} budget={data.flow.budget_usd} bare />
      <div className="og-wait muted">{data.gate ? "Answer the gate in Renders" : "Let the run finish"}: the report lands here.</div>
    </div>
  );
}

export function ReportGlance() {
  const r = useFlow((s) => s.data?.report);
  const nm = useFlow(stepCount);
  if (!r) return <Pending />;
  return (
    <div className="glance">
      <div className="glance-row">
        <FlowBadge testid="flow-report-state" />
        <span className="spacer" />
        <Button size="sm" onClick={() => copy(r)}>Copy</Button>
      </div>
      <CostBar spent={r.cost_usd} budget={r.budget_usd} />
      <div className="glance-numbers">
        <Metric value={nm} label="steps" tone={r.status === "finished" ? "ok" : "bad"} />
        <Metric value={(r.posts || []).length} label="posts" />
        <Metric value={elapsed(r.elapsed_s)} label="time" />
      </div>
      {r.metrics?.summary && <div className="glance-hint mono">{r.metrics.summary}</div>}
    </div>
  );
}

export function ReportDetail() {
  const r = useFlow((s) => s.data?.report);
  const [tab, setTab] = useState<ReportTab>("report");
  if (!r) return <Pending />;
  return (
    <div className="og-report-tabs">
      <ReportTabs value={tab} onChange={setTab} />
      {tab === "coach" ? <CoachCards kind="flow" run={r.run} onApply={applySuggestion} /> : <ReportBody r={r} />}
    </div>
  );
}

function ReportBody({ r }: { r: Report }) {
  return (
    <div className="og-report fl-report">
      <div className="og-report-head">
        <FlowBadge />
        <span className="mono" title={`run ${r.run}`}>{r.name}</span>
        <Button size="sm" onClick={() => copy(r)}>Copy</Button>
      </div>
      {r.stop_reason && <p className="og-stop">{r.stop_reason}</p>}
      <CostBar spent={r.cost_usd} budget={r.budget_usd} />
      <div className="fl-table-wrap">
      <table className="fl-table mono">
        <thead>
          <tr><th>step</th><th>kind</th><th>state</th><th>cost</th><th>time</th><th>rounds</th></tr>
        </thead>
        <tbody>
          {(r.steps || []).map((s) => (
            <tr key={s.id} data-state={s.state} title={s.error || undefined}>
              <td>{s.id}</td><td className="muted">{s.kind}</td><td className="fl-state">{s.state}</td>
              <td>{cost(s.cost_usd)}</td><td>{s.elapsed_s !== undefined ? elapsed(s.elapsed_s) : "-"}</td><td>{s.rounds || 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      <dl className="og-facts mono">
        {(r.artboards || []).map((a) => (
          <div key={a.id} className="fl-fact"><dt>artboard</dt><dd>{a.id} ({a.kind}) · {a.prompt_id}</dd></div>
        ))}
        {(r.posts || []).map((p, i) => (
          <div key={i} className="fl-fact"><dt>post {p.platform}</dt><dd>{p.dry_run ? "dry run" : p.error ? `failed: ${p.error}` : `live, post ${p.post_id}`} · {p.chars} chars · {p.media} media</dd></div>
        ))}
        <div className="fl-fact"><dt>metrics</dt><dd>{r.metrics?.summary || "-"}</dd></div>
      </dl>
    </div>
  );
}

export function ReportSettings() {
  const r = useFlow((s) => s.data?.report);
  return r ? <Button size="sm" onClick={() => copy(r)}>Copy the report text</Button> : <p className="muted">No report yet.</p>;
}

export function useReportMotion(): MotionState {
  const status = useFlow((s) => s.data?.report?.status);
  const doneAt = useFlow((s) => s.doneAt);
  return status ? runMotion(status, false, doneAt) : "none";
}
