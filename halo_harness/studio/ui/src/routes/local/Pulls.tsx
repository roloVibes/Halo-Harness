// A pull's progress (3.3.5.0 R3; routes/local/jobs.ts): the bar, the percent of the layers' bytes, the speed and the
// time left, each titled with where it comes from, and Cancel while it runs (Ollama keeps the layers it has; pulling
// it again starts from them). JobsList is the Jobs list on the Library and Models pages: every pull running and the
// last ended ones, each with its own bar and Cancel. 3.3.5.0 R5: a Hugging Face download is one of them (the file
// moving, the folder it goes into; its Cancel keeps the part file, and downloading again resumes from it).
import { useMemo } from "react";
import { Button } from "../../lib/ui";
import { cancelPull, eta, rate, useJobs } from "./jobs";
import type { PullJob } from "./types";

const state = (j: PullJob) => (!j.done ? "running" : j.ok ? "done" : j.cancelled ? "cancelled" : "failed");

export function PullBar({ j }: { j: PullJob }) {
  const pct = j.percent ?? 0;
  return (
    <div className="lc-pull" data-testid="local-pull-progress" data-state={state(j)} data-percent={j.percent ?? ""} data-name={j.name} data-host={j.host}>
      <span className="lc-pull-bar" aria-hidden="true"><span style={{ width: `${Math.min(100, pct)}%` }} /></span>
      <span className="mono" data-testid="local-pull-percent" title={j.kind === "download" ? "the files' bytes done of their total (the hub's listing)" : "the layers' bytes done of their total (Ollama's pull stream)"}>
        {j.percent != null ? `${j.percent.toFixed(0)}%` : "…"}
      </span>
      <span className="mono muted" data-testid="local-pull-status" title={j.kind === "download" ? "the file moving (the hub's resolve URL)" : "Ollama's own status line"}>{j.status}</span>
      {!j.done && j.speed ? <span className="mono muted" data-testid="local-pull-speed" title="bytes a second over the last 5 s">{rate(j.speed)}</span> : null}
      {!j.done && j.eta != null ? <span className="mono muted" data-testid="local-pull-eta" title="what is left at that speed">{eta(j.eta)}</span> : null}
      {!j.done && (
        <Button size="sm" variant="ghost" onClick={() => void cancelPull(j.job, j.kind)} data-testid="local-pull-cancel"
                title={j.kind === "download" ? "stop it: the part file stays, and downloading again resumes from it"
                  : "stop it: Ollama keeps the layers it has, and pulling it again starts from them"}>Cancel</Button>
      )}
      {j.done && <span className="mono lc-said" data-ok={j.ok || undefined} data-testid="local-pull-said">{j.say}</span>}
      {j.via && j.via !== "this machine" && <span className="mono muted" title="the member pulls; its progress comes with its ledger push">via {j.via}</span>}
    </div>
  );
}

export function JobsList() {
  const all = useJobs((s) => s.jobs); // the store's own object: a new array from a selector would redraw forever
  const list = useMemo(() => Object.values(all).sort((a, b) => Number(a.done) - Number(b.done) || b.started - a.started).slice(0, 8), [all]);
  if (!list.length) return null;
  return (
    <section className="lc-block lc-jobs" aria-label="Jobs" data-testid="local-jobs">
      <div className="rail-label mono">JOBS · {list.filter((j) => !j.done).length} RUNNING</div>
      <ul className="lc-jobs-list">
        {list.map((j) => (
          <li key={j.job} data-testid="local-job" data-name={j.name} data-host={j.host} data-state={state(j)} data-kind={j.kind || "pull"}>
            <span className="mono"><b>{j.name}</b> {j.kind === "download" ? "into" : "on"} {j.host}</span>
            <PullBar j={j} />
          </li>
        ))}
      </ul>
    </section>
  );
}
