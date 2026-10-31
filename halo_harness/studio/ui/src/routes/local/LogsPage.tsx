// Local -> Logs (3.3.6.0 R3, plans/local-model-fit-brief.md Part C's deliverable): a host picker; the host's log
// status line (live / stale / quiet / unreadable / on that machine / missing) with the path, the tail command (Copy)
// and the debug window said as a stated action (Halo never sets it); per model the last load result, the truncations
// of this session, the error lines with times and "crashed here" (LogModelRows.tsx); the bounded tail with its kind
// filter and a Live toggle (LogTail.tsx). Every block has its own "?" help. Nothing opens over the page.
import { useEffect } from "react";
import { Button, Empty } from "../../lib/ui";
import { BlockHelp, LogModelRows } from "./LogModelRows";
import { LogTail } from "./LogTail";
import { copyLine, loadAll, logs, pickHost, useLogs } from "./logstore";
import { loadHosts, useLocal } from "./store";

const STATUS_HELP = "live: the newest log line is newer than the newest call to this host (minus a minute). stale: the " +
  "ledger has calls the log never saw (Ollama writes elsewhere, or the file is an old one). quiet: no calls and no lines " +
  "in the last 15 minutes. On that machine with no ssh entry: a fleet member's push carries its events, else only " +
  "/api/ps says the fit (size_vram under size is a spill). Debug: on when debug-level lines appear.";

function Status() {
  const st = useLogs((s) => s.status);
  const said = useLogs((s) => s.said);
  if (!st) return <div className="mono muted" data-testid="local-logs-status-reading">reading the log status...</div>;
  return (
    <section className="lc-block lg-status" data-testid="local-logs-status" data-state={st.state} aria-label="log status">
      <div className="lg-head">
        <span className="rail-label mono">LOG STATUS</span>
        <BlockHelp text={STATUS_HELP} testid="local-logs-status-help" />
      </div>
      <div className="mono lg-line" data-testid="local-logs-status-line" data-state={st.state} title={st.why || st.line}>{st.line}</div>
      {st.path && <div className="mono muted" data-testid="local-logs-path" title={(st.paths || []).join("\n")}>{st.path}</div>}
      <div className="lg-acts">
        {st.tail_cli && (
          <Button size="sm" onClick={() => copyLine(st.tail_cli)} data-testid="local-logs-copy-tail" title={st.tail_cli}>Copy the tail command</Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => copyLine(st.halo_cli)} data-testid="local-logs-copy-halo" title={st.halo_cli}>
          Copy {st.halo_cli}
        </Button>
      </div>
      <p className="muted lg-debug" data-testid="local-logs-debug">More detail: {st.debug_action}.</p>
      {said && <div className="mono lc-said" data-testid="local-logs-said">{said}</div>}
    </section>
  );
}

export function LogsPage() {
  const hosts = useLocal((s) => s.hosts);
  const host = useLogs((s) => s.host);
  const error = useLogs((s) => s.error);
  const names = (hosts || []).filter((h) => h.source === "configured" && h.kind === "Ollama").map((h) => h.name);
  const picked = names.includes(host) ? host : names[0] || "";
  useEffect(() => {
    void loadHosts();
  }, []);
  useEffect(() => {
    if (!picked) return;
    if (picked !== logs.get().host) {
      pickHost(picked);
    } else {
      loadAll(picked);
    }
  }, [picked]);
  if (!hosts) return <div className="mono muted">reading the hosts...</div>;
  if (!names.length) return <Empty title="No Ollama host yet" body="Add one in Setup -> Providers -> Ollama: its log shows here." testid="local-logs-none" />;
  return (
    <div className="lg-page" data-testid="local-logs" data-host={picked}>
      <label className="mono muted lg-pick">host{" "}
        <select value={picked} onChange={(e) => pickHost(e.target.value)} data-testid="local-logs-host" aria-label="the host whose log this is">
          {names.map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      {error && <div className="mono lc-said" data-testid="local-logs-error">{error}</div>}
      <Status />
      <LogModelRows />
      <LogTail />
    </div>
  );
}
