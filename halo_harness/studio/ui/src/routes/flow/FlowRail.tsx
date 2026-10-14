// The Flow section's block in the rail: the runs, newest first (a run that
// waits on you pulses amber; click one to open it), then the flows a run can
// start from (click one to load it into the Start view's form).
import { useEffect } from "react";
import { clock, cost } from "../orchestra/format";
import { Button } from "../../lib/ui";
import { pickTemplate, runMotion, setView, useFlow } from "./store";
import { openRun, startFlow } from "./sync";

export function FlowRail() {
  useEffect(() => startFlow(), []);
  const runs = useFlow((s) => s.runs);
  const templates = useFlow((s) => s.templates);
  const current = useFlow((s) => s.runId);
  const doneAt = useFlow((s) => s.doneAt);
  return (
    <>
      <section className="rail-group" aria-label="Flow runs">
        <Button size="sm" variant="primary" onClick={() => setView("start")} title="The Start view: write a brief, then Run">
          New run
        </Button>
        <div className="rail-label mono">RUNS · {runs.length}</div>
        {runs.slice(0, 12).map((r) => {
          const state = r.waiting_step ? "waiting" : r.status;
          return (
            <button key={r.run} className="rail-item fl-rail-run" aria-current={r.run === current} onClick={() => void openRun(r.run)} title={`${r.run} · ${r.name} · ${r.project || "no project"} · ${cost(r.cost_usd)} · ${clock(r.created)}`} data-testid="flow-rail-run">
              <span className="og-run-dot fl-dot" data-state={state} data-motion={runMotion(state, !!r.waiting_step, r.run === current ? doneAt : 0)} />
              <span className="rail-item-text mono">{r.run.slice(9)}</span>
              <span className="badge" data-state={state}>{r.waiting_step ? "waits on you" : r.live ? "live" : r.status}</span>
            </button>
          );
        })}
        {!runs.length && <p className="rail-note">Press New run and write a brief to make the first one.</p>}
      </section>
      <section className="rail-group" aria-label="Flows">
        <div className="rail-label mono">FLOWS · {templates.length}</div>
        {templates.map((t) => (
          <button
            key={t.source + t.name}
            className="rail-item fl-rail-flow"
            disabled={!!t.error}
            onClick={() => {
              pickTemplate(t.name);
              setView("start");
            }}
            title={t.error || `${t.steps.map((s) => s.id).join(" -> ")}`}
          >
            <span className="rail-item-text">{t.name}</span>
            <span className="mono muted">{t.source} · {t.steps.length} steps</span>
          </button>
        ))}
      </section>
    </>
  );
}
