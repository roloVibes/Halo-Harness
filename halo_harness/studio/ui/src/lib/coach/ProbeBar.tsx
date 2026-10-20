// The coach's Probe (3.1.6.0 R2) on an Orchestra run's Coach tab: the button
// in the header row (lib/coach/probe.ts asks for the cost line first), the
// confirm under it ("probe: N runs, up to $X", Run the probe / Cancel: nothing
// runs before), and the progress line while the probe runs (its step lines
// from the live feed; the card leads the tab once it ends). ContrastTable is
// the probe card's table: the run itself, then each candidate, the pick marked.
import { useEffect } from "react";
import { Button } from "../ui";
import { askProbe, cancelProbe, followProbe, startProbe } from "./probe";
import { keyOf, useCoach } from "./store";
import type { ProbeRow } from "./types";

const money = (x: number | null | undefined) => (x === null || x === undefined ? "-" : `$${Number(x).toFixed(4)}`);

function useProbe(run: string) {
  const key = keyOf("orchestra", run);
  const ui = useCoach((s) => s.probe[key]);
  const status = useCoach((s) => s.runs[key]?.result?.probe);
  const running = status?.state === "running" || !!status?.live || ui?.busy === "start";
  return { ui: ui || {}, status: status || null, running };
}

export function ProbeButton({ run }: { run: string }) {
  const { ui, running } = useProbe(run);
  useEffect(() => followProbe(run), [run, running]); // a probe found running (here or from `halo coach --probe`) is followed
  return (
    <Button size="sm" variant="default" disabled={running || ui.busy === "estimate" || !!ui.open}
            onClick={() => void askProbe(run)} data-testid="coach-probe"
            title="Runs the goal again under two candidate setups the run's lead drafts, has an anonymized judge compare what each delivered with this run, and offers what wins as one card. The cost shows first; nothing runs until you confirm.">
      {running ? "Probing..." : "Probe"}
    </Button>
  );
}

export function ProbePanel({ run }: { run: string }) {
  const { ui, status, running } = useProbe(run);
  const line = ui.line || (status?.state === "running" ? status.line : "");
  return (
    <>
      {ui.open && ui.estimate && (
        <div className="cc-probe-confirm" data-testid="coach-probe-confirm" role="group" aria-label="Confirm the probe">
          <span className="glance-kicker mono">PROBE</span>
          <span className="mono cc-probe-cost" data-testid="coach-probe-cost">{ui.estimate.line}</span>
          <span className="muted cc-hint">Each probe run starts from this run's base commit, stops at its cap, and is removed after the compare (its report and patch stay).</span>
          <div className="cc-actions">
            <span className="spacer" />
            <Button size="sm" variant="ghost" onClick={() => cancelProbe(run)} data-testid="coach-probe-cancel"
                    title="Close; nothing runs">Cancel</Button>
            <Button size="sm" variant="primary" disabled={ui.busy === "start"} onClick={() => void startProbe(run)}
                    data-testid="coach-probe-run" title="Start the probe now">{ui.busy === "start" ? "Starting..." : "Run the probe"}</Button>
          </div>
        </div>
      )}
      {running && (
        <div className="cc-probe-line mono" data-testid="coach-probe-progress" aria-live="polite">
          <span className="cc-probe-dot" aria-hidden="true" />{line || "the probe is running..."}
        </div>
      )}
      {!running && status?.state === "failed" && (
        <div className="cc-lead-error mono" data-testid="coach-probe-failed">the probe stopped: {status.error || status.line}</div>
      )}
    </>
  );
}

function tests(r: ProbeRow): string {
  if (r.tests_ok === null || r.tests_ok === undefined) return r.status || "-";
  const base = (r.tests_ok ? "pass" : "fail") + (r.passed !== null && r.passed !== undefined ? ` ${r.passed}` : "");
  return base + (typeof r.tests_delta === "number" ? ` (${r.tests_delta >= 0 ? "+" : ""}${r.tests_delta})` : "");
}

function steps(r: ProbeRow): string {
  if (r.steps === null || r.steps === undefined) return "-";
  return `${r.steps}` + (typeof r.steps_delta === "number" ? ` (${r.steps_delta >= 0 ? "+" : ""}${r.steps_delta})` : "");
}

export function ContrastTable({ rows }: { rows: ProbeRow[] }) {
  return (
    <div className="cc-contrast-wrap">
      <table className="cc-contrast mono" data-testid="coach-contrast" aria-label="The probe's contrast">
        <thead>
          <tr><th>run</th><th>tests</th><th>cost</th><th>steps</th><th>judge</th><th>won</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-testid="coach-contrast-row" data-id={r.id} data-kind={r.kind} data-picked={r.picked ? "1" : ""}>
              <td>{r.id === "reference" ? "the run itself" : `${r.kind} · ${r.id}`}</td>
              <td>{tests(r)}</td>
              <td>{money(r.cost_usd)}{typeof r.cost_x === "number" ? ` (${r.cost_x.toFixed(2)}x)` : ""}</td>
              <td>{steps(r)}</td>
              <td>{r.rank ?? "-"}</td>
              <td>{(r.wins || []).join(", ") || (r.id === "reference" || r.status === "finished" ? "" : r.stop_reason || r.status || "")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
