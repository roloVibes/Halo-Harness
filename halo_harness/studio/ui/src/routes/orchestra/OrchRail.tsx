// The Orchestra section's runs: in the rail (New run, which opens the Start
// view, then the runs of this repo, newest first; click one to open it) and
// on the Start view (the past runs as cards).
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { clock, cost, short } from "./format";
import { runMotion, setView, useOrch } from "./store";
import { openRun, startOrchestra } from "./sync";

export function OrchestraRail() {
  useEffect(() => startOrchestra(), []);
  const runs = useOrch((s) => s.runs);
  const current = useOrch((s) => s.runId);
  const doneAt = useOrch((s) => s.doneAt);
  return (
    <section className="rail-group" aria-label="Orchestra runs">
      <Button size="sm" variant="primary" onClick={() => setView("start")} title="The Start view: write a goal, then Run">
        New run
      </Button>
      <div className="rail-label mono">RUNS · {runs.length}</div>
      {runs.slice(0, 12).map((r) => (
        <button
          key={r.run_id}
          className="rail-item og-rail-run"
          aria-current={r.run_id === current}
          onClick={() => void openRun(r.run_id)}
          title={`${r.run_id} · ${r.goal_what} · ${r.workers} workers · ${cost(r.cost_usd)} · ${clock(r.created)}`}
          data-testid="orchestra-rail-run"
        >
          <span className="og-run-dot" data-state={r.state} data-motion={runMotion(r.state, r.run_id === current ? doneAt : 0)} />
          <span className="rail-item-text">{short(r.goal_what, 34) || r.run_id}</span>
          <span className="badge" data-state={r.state}>{r.state}</span>
        </button>
      ))}
      {!runs.length && <p className="rail-note">No run in this repo yet: write a goal on the Start view and press Run.</p>}
    </section>
  );
}

export function PastRuns() {
  const runs = useOrch((s) => s.runs);
  return (
    <section className="fl-start-runs" aria-label="Past runs">
      <div className="rail-label mono">PAST RUNS · {runs.length}</div>
      {runs.slice(0, 8).map((r) => (
        <button key={r.run_id} className="og-run" onClick={() => void openRun(r.run_id)}>
          <span className="og-run-dot" data-state={r.state} data-motion={runMotion(r.state, 0)} />
          <span className="mono og-run-id">{r.run_id}</span>
          <span className="og-run-what">{short(r.goal_what, 60)}</span>
          <span className="mono muted">
            {r.state} · {r.workers} workers · {cost(r.cost_usd)} · {clock(r.created)}
          </span>
        </button>
      ))}
      {!runs.length && <p className="muted">Your first run shows up here; open any run to see its panels.</p>}
    </section>
  );
}
