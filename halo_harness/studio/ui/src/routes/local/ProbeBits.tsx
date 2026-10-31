// A Models row's battery bits (3.3.6.0 R1; routes/local/probes.ts): the Probe action (local-model-probe) whose
// title is the cost line ("about 9 requests to <model> on <host> (one 1 px image, one tiny call, for the eyes), 1-3 minutes, no cost; it loads the model") and
// the `halo models probe` line, the progress strip while it runs (one step per probe), the "probed <date> ·
// re-probe" mark, and the twin chips: a fitted twin with its verify line, a raw library tag with "delete the raw
// tag, keep the twin" once its twin is verified.
import { Button } from "../../lib/ui";
import { openAct } from "./ctl";
import { costLine, probeFor, probeKey, probeLine, startProbe, useProbes } from "./probes";
import { useLocal } from "./store";
import type { ModelEntry } from "./types";

export function ProbeAction({ m, host }: { m: ModelEntry; host: string }) {
  const job = useProbes((s) => probeFor(s, host, m.model));
  const ctl = useLocal((s) => s.hosts?.find((h) => h.name === host)?.controls);
  const off = ctl && !ctl.ok ? ctl.why : "";
  const probed = !!m.card?.probe;
  const running = !!job && !job.done;
  return (
    <Button size="sm" disabled={running || !!off} onClick={() => void startProbe(host, m.model, probed)} data-testid="local-model-probe"
            data-probed={probed || undefined} title={off || `${costLine(m.model, host)} -- ${probeLine(m.model, host, probed)}`}>
      {running ? "Probing..." : probed ? "Re-probe" : "Probe"}
    </Button>
  );
}

export function ProbeStrip({ m, host }: { m: ModelEntry; host: string }) {
  const job = useProbes((s) => probeFor(s, host, m.model));
  const said = useProbes((s) => s.said[probeKey(host, m.model)]);
  if (said) return <div className="mono lc-said" data-testid="local-probe-said">{said}</div>;
  if (!job) return null;
  const pct = job.of ? Math.round((100 * Math.min(job.step, job.of)) / job.of) : 0;
  return (
    <div className="mprobe-strip mono" data-testid="local-probe-strip" data-done={job.done || undefined} data-ok={job.ok || undefined}>
      {!job.done && <span className="muted" data-testid="local-probe-cost">{job.cost}</span>}
      <span className="mprobe-bar" aria-hidden="true"><span className="mprobe-fill" style={{ width: `${job.done ? 100 : pct}%` }} /></span>
      <span data-testid="local-probe-step">{job.done ? (job.ok ? job.say : job.error || job.say) : `${job.say}`}</span>
    </div>
  );
}

export function ProbedMark({ m, host }: { m: ModelEntry; host: string }) {
  const p = m.card?.probe;
  if (!p) return <span className="mono muted mprobe-mark" data-testid="local-model-probed" data-probed="no" title="every value is expected until the battery runs">not probed</span>;
  return (
    <span className="mono muted mprobe-mark" data-testid="local-model-probed" data-probed="yes" title={`${p.line}${p.stale ? " (an older probe set: re-probe)" : ""}`}>
      probed {p.date}{p.stale ? " (old)" : ""} ·{" "}
      <button type="button" className="mprobe-link" onClick={() => void startProbe(host, m.model, true)} data-testid="local-model-reprobe"
              title={probeLine(m.model, host, true)}>re-probe</button>
    </span>
  );
}

export function TwinChips({ m, host }: { m: ModelEntry; host: string }) {
  if (m.twin) {
    return (
      <span className="og-chip mono mprobe-twin" data-testid="local-model-twin" data-state={m.twin.state} title={m.twin.line}>
        twin of {m.twin.of} · {m.twin.state}
      </span>
    );
  }
  if (!m.raw) return null;
  return (
    <span className="mprobe-raw" data-testid="local-model-raw" data-verified={m.raw.verified || undefined}>
      <span className="og-chip mono" title={`raw library tag; fitted twin${m.raw.twins.length > 1 ? "s" : ""}: ${m.raw.twins.join(", ")}`}>raw tag</span>
      {m.raw.offer && (
        <button type="button" className="mprobe-link mono" onClick={() => openAct("delete", host, m)} data-testid="local-model-raw-offer" title={m.raw.offer}>
          delete the raw tag, keep the twin
        </button>
      )}
    </span>
  );
}
