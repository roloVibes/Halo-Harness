// The Orchestra section's runs: in the header's "+" menu (3.3.2.0 R2; the
// expanded rail before): New run, which opens the Start view, then the runs of
// this repo, newest first (click one to open it); and on the Start view (the
// past runs as cards).
import { useEffect } from "react";
import type { MenuGroup } from "../../lib/ui/Menu";
import { clock, cost, short } from "./format";
import { runMotion, setView, useOrch } from "./store";
import { openRun, startOrchestra } from "./sync";

/** Orchestra's own group in the "+" menu (routes/index.tsx `menu`): New run, then up to 12 runs. */
export function useOrchestraMenu(): MenuGroup {
  useEffect(() => startOrchestra(), []);
  const runs = useOrch((s) => s.runs);
  const current = useOrch((s) => s.runId);
  const head = { id: "new-run", label: "New run", icon: "plus", word: "start", title: "The Start view: write a goal, then Run", testid: "orchestra-new-run", run: () => setView("start") };
  return {
    name: `RUNS · ${runs.length}`,
    rows: [head, ...runs.slice(0, 12).map((r) => ({
      id: "run-" + r.run_id,
      label: short(r.goal_what, 34) || r.run_id,
      icon: "orchestra",
      badges: [r.state],
      word: r.run_id === current ? "open now" : "open",
      current: r.run_id === current,
      title: `${r.run_id} · ${r.goal_what} · ${r.workers} workers · ${cost(r.cost_usd)} · ${clock(r.created)}`,
      testid: "orchestra-menu-run",
      data: { run: r.run_id },
      run: () => void openRun(r.run_id),
    }))],
  };
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
