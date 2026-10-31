// The Download and verify jobs in Local's Jobs list (3.3.6.0 R2; routes/local/verify.ts): each job's two stages
// side by side -- the pull (its bar from jobs.ts) and the battery (its step from probes.ts) -- then the role offer.
import { useMemo } from "react";
import { useJobs } from "./jobs";
import { useProbes } from "./probes";
import { PullBar } from "./Pulls";
import { useVerify } from "./verify";

export function VerifyList() {
  const all = useVerify((s) => s.jobs);
  const pulls = useJobs((s) => s.jobs);
  const probes = useProbes((s) => s.jobs);
  const list = useMemo(() => Object.values(all).sort((a, b) => Number(a.done) - Number(b.done) || b.started - a.started).slice(0, 6), [all]);
  if (!list.length) return null;
  return (
    <section className="lc-block lc-jobs" aria-label="Download and verify" data-testid="local-verify-jobs">
      <div className="rail-label mono">DOWNLOAD AND VERIFY · {list.filter((j) => !j.done).length} RUNNING</div>
      <ul className="lc-jobs-list">
        {list.map((j) => {
          const pull = j.pull_job ? pulls[j.pull_job] : undefined;
          const probe = j.probe_job ? probes[j.probe_job] : undefined;
          const pullDone = j.stage !== "pull" || (pull?.done && pull.ok);
          return (
            <li key={j.job} data-testid="local-verify-row" data-name={j.name} data-stage={j.stage} data-done={j.done || undefined} data-ok={j.ok || undefined}>
              <span className="mono"><b>{j.name}</b> on {j.host}</span>
              <span className="mono ls-stage" data-testid="local-verify-stage" data-step="pull" data-state={pullDone ? "done" : "running"}>
                1 pull {pullDone ? "✓" : "…"}
              </span>
              {pull && !pullDone && <PullBar j={pull} />}
              <span className="mono ls-stage" data-testid="local-verify-stage" data-step="probe"
                    data-state={j.stage === "pull" ? "waiting" : j.stage === "probe" ? "running" : j.ok ? "done" : "failed"}>
                2 probe {j.stage === "probe" ? (probe ? `${probe.step}/${probe.of} ${probe.probe}` : "…") : j.stage === "pull" ? "" : j.ok ? "✓" : "✗"}
              </span>
              {j.done && <span className="mono lc-said" data-ok={j.ok || undefined}>{j.offer ? j.offer.line : j.say}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
