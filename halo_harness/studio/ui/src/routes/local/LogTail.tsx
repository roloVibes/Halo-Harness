// Local -> Logs, the bounded tail (3.3.6.0 R3; GET local/host/<n>/log?n=200&kind=): the newest 200 lines of the
// host's server log (its rotation set, journald, or that machine's over ssh), each marked fit / headroom /
// truncation / failure; the kind filter; Live reads it again every LIVE_MS while it is on and the page is shown
// (a poll, never a stream), the status and the per-model rows with it. The tail line it equals is in the title.
import { useEffect } from "react";
import { BlockHelp } from "./LogModelRows";
import { LIVE_MS, LOG_KINDS, loadAll, setKind, setLive, useLogs } from "./logstore";

const HELP = "The newest 200 lines, read when the page opens and on Live every 5 seconds. fit: the load's lines " +
  "(offloaded layers, KV buffers, graph splits); headroom: the memory the scheduler placed it against; truncation: a " +
  "prompt cut to fit the window or a reply cut at it; failure: CUDA errors, a runner that died, 500s, a client that " +
  "gave up. The file can hold invalid UTF-8: it is read as bytes and shown with a replacement mark.";

function at(t: number | null): string {
  return t ? new Date(t * 1000).toLocaleTimeString() : "";
}

export function LogTail() {
  const tail = useLogs((s) => s.tail);
  const kind = useLogs((s) => s.kind);
  const live = useLogs((s) => s.live);
  const host = useLogs((s) => s.host);
  useEffect(() => {
    if (!live || !host) return;
    const id = window.setInterval(() => {
      if (!document.hidden) loadAll(host);
    }, LIVE_MS);
    return () => window.clearInterval(id);
  }, [live, host]);
  return (
    <section className="lc-block lg-tail" data-testid="local-logs-tail" data-kind={kind} aria-label="the log's newest lines">
      <div className="lg-head">
        <span className="rail-label mono">THE NEWEST LINES</span>
        <BlockHelp text={HELP} testid="local-logs-tail-help" />
        <span className="lg-kinds" role="group" aria-label="which lines">
          {LOG_KINDS.map((k) => (
            <button key={k} type="button" className={"og-chip mono lg-kind" + (k === kind ? " on" : "")} aria-pressed={k === kind}
                    onClick={() => setKind(k)} data-testid="local-logs-kind" data-kind={k}>{k}</button>
          ))}
        </span>
        <span className="spacer" />
        <label className="mono muted lg-live" title={`read it again every ${LIVE_MS / 1000} s while this page is shown`}>
          <input type="checkbox" checked={live} onChange={(e) => setLive(e.target.checked)} data-testid="local-logs-live" /> Live
        </label>
      </div>
      {tail && <div className="mono muted" data-testid="local-logs-source" title={tail.cli}>{tail.source || tail.path}</div>}
      {!tail ? <div className="mono muted">reading the log...</div> : tail.why
        ? <div className="mono muted" data-testid="local-logs-tail-why">{tail.why}</div>
        : tail.lines.length === 0
          ? <div className="mono muted" data-testid="local-logs-tail-none">no {kind === "all" ? "" : `${kind} `}lines in the newest {tail.n}</div>
          : (
            <ol className="lg-lines mono" data-testid="local-logs-lines">
              {tail.lines.map((l, i) => (
                <li key={`${i}|${l.text.slice(0, 40)}`} data-testid="local-logs-line" data-group={l.group || ""} title={at(l.at)}>
                  <span className="lg-group">{l.group || ""}</span>{l.text}
                </li>
              ))}
            </ol>
          )}
    </section>
  );
}
