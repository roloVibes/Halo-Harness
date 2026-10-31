// Local -> Logs, per model (3.3.6.0 R3; GET local/host/<n>/log/models): the last load result as the server log
// (or /api/ps) says it -- layers on the GPU, where the KV cache sits, the graph splits, the measured tok/s, when --
// with the fit badge's state; the truncations of this session (the log's limit / prompt / window); the error lines
// with their times; "crashed here" with the fingerprint's line (halo ollama crashes --why).
import { useLogs, type LogModel } from "./logstore";

/** A block's own "?": what it shows, folded until asked (no pop-up). */
export function BlockHelp({ text, testid }: { text: string; testid: string }) {
  return (
    <details className="lg-help" data-testid={testid}>
      <summary className="mono" aria-label="what this block shows">?</summary>
      <p className="muted">{text}</p>
    </details>
  );
}

const HELP = "Each model this host has or its log names. Last load: the newest load-result line (offloaded N/N layers, " +
  "graph splits, the CUDA and CPU KV buffers) or the steward's /api/ps reading, whichever is newer, and the tok/s the " +
  "ledger measured. Spilled means part of it runs on the CPU. Truncations are the log's 'truncating input prompt' lines " +
  "since the newest session that called this host began; errors are the last day's.";

function when(at: string | null): string {
  if (!at) return "";
  const t = Date.parse(at);
  return Number.isFinite(t) ? new Date(t).toLocaleTimeString() : "";
}

function kvWhere(m: LogModel): string {
  const g = m.load.kv_gpu_mib, c = m.load.kv_cpu_mib;
  if (c) return `KV ${g ? `${g} MiB on the GPU + ` : ""}${c} MiB on the CPU`;
  return g ? `KV ${g} MiB on the GPU` : "";
}

function Row({ m }: { m: LogModel }) {
  const l = m.load;
  const facts = [l.layers ? `${l.layers[0]}/${l.layers[1]} layers` : "", kvWhere(m), l.splits != null ? `splits = ${l.splits}` : "",
    l.tok_s != null ? `${Math.round(l.tok_s)} tok/s` : "", l.window ? `window ${l.window.toLocaleString("en-US")}` : ""].filter(Boolean);
  return (
    <li className="lg-model" data-testid="local-logs-model" data-model={m.model} data-load={l.state}>
      <div className="lg-model-top">
        <b className="mono">{m.model}</b>
        <span className="og-chip mono lg-fit" data-testid="local-logs-load" data-state={l.state}
              title={`the last load, from ${l.source || "nothing yet"}`}>{l.line}</span>
        {m.crashed && <span className="og-chip mono ls-crash-chip" data-testid="local-logs-crashed" title={`${m.crashed.line} (halo ollama crashes --why)`}>
          crashed here
        </span>}
        <span className="spacer" />
        {l.at && <span className="mono muted" title="when that load was seen">{when(l.at)}</span>}
      </div>
      {facts.length > 0 && <div className="mono muted" data-testid="local-logs-load-facts">{facts.join(" · ")}</div>}
      {m.crashed && <div className="mono lg-crash" data-testid="local-logs-crash-line">{m.crashed.line}</div>}
      {m.truncations.map((t) => (
        <div key={`t|${t.at}`} className="mono lg-trunc" data-testid="local-logs-truncation" title={t.say}>
          {when(t.at)} cut at {t.limit?.toLocaleString("en-US")} of {t.prompt?.toLocaleString("en-US")} tokens
          {t.window_sent ? ` (the request's window ${t.window_sent.toLocaleString("en-US")})` : ""}
        </div>
      ))}
      {m.errors.map((e) => (
        <div key={`e|${e.at}|${e.kind}`} className="mono lg-error" data-testid="local-logs-error-line" data-kind={e.kind}>
          {when(e.at)} {e.kind}: {e.say}
        </div>
      ))}
    </li>
  );
}

export function LogModelRows() {
  const models = useLogs((s) => s.models);
  return (
    <section className="lc-block" data-testid="local-logs-models" aria-label="per model">
      <div className="lg-head">
        <span className="rail-label mono">PER MODEL</span>
        <BlockHelp text={HELP} testid="local-logs-models-help" />
        {models?.session?.since ? <span className="mono muted">this session since {new Date(models.session.since * 1000).toLocaleTimeString()}</span> : null}
      </div>
      {!models ? <div className="mono muted">reading the models...</div> : models.models.length === 0
        ? <div className="mono muted" data-testid="local-logs-models-none">no model on this host yet</div>
        : <ul className="lg-models">{models.models.map((m) => <Row key={m.model} m={m} />)}</ul>}
    </section>
  );
}
