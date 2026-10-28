// The Ollama panel's fit plan and traffic timeline (3.3.4.0 R5). The plan (ollama_steward/fit.py) says whether
// the models the halos ask for fit the card together; each option says what you lose; an option with profile
// changes has Apply (through the same guards as a finding's); a server-side hint has Copy, which copies the
// exact line (an env line such as OLLAMA_KV_CACHE_TYPE=q8_0, or a command): nothing here changes the server.
// The timeline: the last hour's calls per minute as a sparkline, a trim and a cut marked on their minute.
import { Button, Icon } from "../../lib/ui";
import { applyChange, copyHint, gib, useOllama, type Bucket, type Plan, type PlanOption } from "./ostore";

function Option({ o, chosen, i }: { o: PlanOption; chosen: boolean; i: number }) {
  const busy = useOllama((s) => s.busy);
  const copied = useOllama((s) => s.copied);
  const h = o.server_hint;
  return (
    <li className="oll-option" data-testid="ollama-option" data-kind={o.kind} data-chosen={chosen || undefined} data-fits={o.fits ? "yes" : "no"}>
      <div className="oll-option-top">
        <span className="mono">{chosen ? "★" : `${i + 1}.`}</span>
        <span>{o.says}</span>
      </div>
      <div className="muted oll-lose">you lose: {o.lose}</div>
      {o.changes.length > 0 && (
        <div className="oll-actions">
          <span className="mono muted">{o.changes.map((c) => `${c.key}: ${c.field} → ${String(c.to)}`).join(" · ")}</span>
          <span className="spacer" />
          <Button size="sm" variant={chosen ? "primary" : "default"} disabled={!!busy || !o.fits}
                  onClick={() => o.changes.forEach((c) => void applyChange(c, `the fit plan: ${o.says}`))} data-testid="ollama-plan-apply">Apply</Button>
        </div>
      )}
      {h && (
        <div className="oll-hint">
          <code className="mono" data-testid="ollama-hint-line">{h.line}</code>
          <Button size="sm" variant="ghost" icon={<Icon name="copy" />} onClick={() => copyHint(h.line)} data-testid="ollama-copy-hint"
                  data-copied={copied === h.line ? h.line : undefined} title="copy the exact line; set it on the server yourself">
            {copied === h.line ? "Copied" : "Copy"}
          </Button>
          <span className="muted">costs: {h.cost}</span>
        </div>
      )}
    </li>
  );
}

export function PlanBlock({ plan }: { plan: Plan | null }) {
  if (!plan) return null;
  return (
    <section className="oll-block" aria-label="Fit plan" data-testid="ollama-plan">
      <div className="rail-label mono">FIT PLAN · THE CARD</div>
      <p className="oll-says" data-fits={plan.fits_now ? "yes" : "no"}>{plan.says}</p>
      {plan.models.length > 0 && (
        <div className="mono muted oll-needs">{plan.models.map((m) => `${m.model} at ${m.window}: ${gib(m.need)}`).join(" · ")}</div>
      )}
      {plan.options.length > 0 && (
        <ol className="oll-options">
          {plan.options.map((o, i) => (
            <Option key={o.kind + i} o={o} i={i} chosen={i === plan.chosen} />
          ))}
        </ol>
      )}
      {plan.missing.length > 0 && <p className="muted">Not planned (no catalog row or window): {plan.missing.join(", ")}</p>}
    </section>
  );
}

const W = 300;
const H = 44;

export function Timeline({ buckets }: { buckets: Bucket[] | undefined }) {
  if (!buckets) return <div className="oll-timeline muted mono">reading the last hour...</div>;
  const peak = Math.max(1, ...buckets.map((b) => b.calls));
  const n = Math.max(1, buckets.length - 1);
  const x = (i: number) => (i / n) * W;
  const y = (v: number) => H - 4 - (v / peak) * (H - 10);
  const pts = buckets.map((b, i) => `${x(i).toFixed(1)},${y(b.calls).toFixed(1)}`).join(" ");
  const calls = buckets.reduce((m, b) => m + b.calls, 0);
  return (
    <section className="oll-block" aria-label="Traffic">
      <div className="rail-label mono">TRAFFIC · CALLS PER MINUTE, THE LAST HOUR</div>
      <svg className="oll-timeline" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" data-testid="ollama-timeline"
           data-buckets={buckets.length} data-calls={calls} role="img" aria-label={`${calls} calls in the last hour`}>
        <line className="oll-axis" x1={0} y1={H - 4} x2={W} y2={H - 4} />
        <polyline className="oll-line" points={pts} fill="none" />
        {buckets.map((b, i) =>
          b.trims || b.cuts || b.errors ? (
            <circle key={b.t} className="oll-mark" data-testid="ollama-mark" data-kind={b.cuts ? "cut" : b.trims ? "trim" : "error"}
                    cx={x(i)} cy={y(b.calls)} r={2.6}>
              <title>{new Date(b.t * 1000).toLocaleTimeString()}: {b.calls} calls, {b.trims} trims, {b.cuts} cuts, {b.errors} errors</title>
            </circle>
          ) : null,
        )}
      </svg>
      <div className="mono muted oll-legend">
        {calls} calls · <span className="oll-key" data-kind="trim">●</span> trim · <span className="oll-key" data-kind="cut">●</span> cut ·{" "}
        <span className="oll-key" data-kind="error">●</span> error
      </div>
    </section>
  );
}
