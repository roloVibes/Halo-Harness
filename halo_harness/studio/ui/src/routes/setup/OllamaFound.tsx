// The Ollama card's finders (3.3.0.0 R5): **Find Ollama servers** asks this
// machine's doors at once (OLLAMA_HOST, loopback on `ollama.discover.ports`,
// this machine's LAN address, Docker, WSL; about 4 s); **Scan this network**
// sweeps the /24 of this machine plus `ollama.discover.subnets` as a
// background job (10 s cap) with a live line "scanning <subnet> · N s" and a
// Stop. Every server found is a row: name, address, version, the models it
// serves, and "configured" or a tick; **Add the ticked** writes the ticked
// ones as `ollama.hosts` entries (an existing host is never repointed, the
// first host stays the default) and the Models refresh runs for them.
// `halo ollama discover [--lan] [--add]` does the same from a terminal.
import { useEffect } from "react";
import { Button } from "../../lib/ui";
import { CardLines, useCards } from "./cards";
import { addTicked, findServers, running, scanNetwork, startDiscover, stopJob, tick, useDiscover, type FoundRow } from "./discover";
import { OllamaMeasure } from "./OllamaMeasure";
import { useSetup } from "./store";

type Block = { ports?: number[]; subnets?: string[] };

function modelsText(models: string[]): string {
  if (!models.length) return "no models pulled yet";
  return `${models.length} model${models.length === 1 ? "" : "s"}: ${models.join(", ")}`;
}

function PortsLine() {
  const found = useDiscover((s) => s.ports);
  const block = useSetup((s) => (s.data as (Record<string, unknown> & { ollama_discover?: Block }) | null)?.ollama_discover);
  const ports = found || block?.ports || [];
  const subnets = block?.subnets || [];
  return (
    <span className="su-note muted" data-testid="setup-ollama-ports">
      Find asks this machine on {ports.length ? `port${ports.length === 1 ? "" : "s"} ${ports.join(", ")} (ollama.discover.ports)` : "the ports in ollama.discover.ports"};
      {" "}Scan sweeps this machine's /24{subnets.length ? ` and ${subnets.join(", ")}` : ""} (ollama.discover.subnets). Nothing scans on its own.
    </span>
  );
}

function ScanLine() {
  const scan = useDiscover((s) => s.scan);
  if (!scan || !scan.job) return null;
  const on = running(scan);
  const text = on ? `${scan.note || "starting the scan"} · ${Math.round(scan.elapsed || 0)} s` : scan.note || scan.state;
  return (
    <div className="su-note mono" data-testid="setup-ollama-scan-line" data-state={scan.state}>
      {text}
    </div>
  );
}

function Row({ r, on, busy }: { r: FoundRow; on: boolean; busy: boolean }) {
  return (
    <tr data-testid="setup-found-row" data-url={r.url} data-name={r.name} data-configured={r.configured || undefined}>
      <td>
        {r.configured ? (
          <span className="su-on mono" data-testid="setup-found-configured">configured</span>
        ) : (
          <label className="mono" title={`add ${r.name} (${r.url}) to ollama.hosts`}>
            <input type="checkbox" checked={on} disabled={busy} onChange={(e) => tick(r.url, e.target.checked)}
                   data-testid="setup-found-tick" data-url={r.url} aria-label={`tick ${r.name}`} />
          </label>
        )}
      </td>
      <td className="mono">{r.name}</td>
      <td className="mono muted">{r.url.replace(/^https?:\/\//, "")}</td>
      <td className="mono muted">{r.version || "?"}</td>
      <td className="mono muted su-wrap" data-testid="setup-found-models">{modelsText(r.models)}</td>
    </tr>
  );
}

export function OllamaFound() {
  useEffect(() => startDiscover(), []);
  const rows = useDiscover((s) => s.rows);
  const ticked = useDiscover((s) => s.ticked);
  const notes = useDiscover((s) => s.notes);
  const busy = useDiscover((s) => s.busy);
  const scanning = useDiscover((s) => running(s.scan));
  const cardBusy = useCards((s) => s.busy);
  const count = rows.filter((r) => !r.configured && ticked[r.url]).length;
  return (
    <div className="su-form" data-testid="setup-ollama-found">
      <div className="su-card-row">
        <Button size="sm" disabled={!!busy || !!cardBusy} onClick={() => void findServers()} data-testid="setup-ollama-find"
                title="Ask this machine's doors (OLLAMA_HOST, loopback, this machine's LAN address, Docker, WSL) at once, about 4 s">
          {busy === "find" ? "Finding..." : "Find Ollama servers"}
        </Button>
        <Button size="sm" disabled={scanning} onClick={() => void scanNetwork()} data-testid="setup-ollama-scan"
                title="Sweep this machine's /24 and ollama.discover.subnets for Ollama (a 10 s cap)">
          {scanning ? "Scanning..." : "Scan this network"}
        </Button>
        {scanning && (
          <Button size="sm" variant="ghost" onClick={() => void stopJob("scan")} data-testid="setup-ollama-scan-stop">
            Stop
          </Button>
        )}
      </div>
      <PortsLine />
      <ScanLine />
      {notes.length > 0 && (
        <div className="su-note muted mono" data-testid="setup-ollama-notes">
          {notes.join(" · ")}
        </div>
      )}
      {rows.length > 0 && (
        <>
          <table className="su-table" data-testid="setup-found">
            <thead>
              <tr>
                {["", "name", "address", "version", "models"].map((h) => (
                  <th key={h || "tick"} className="mono">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Row key={r.url} r={r} on={!!ticked[r.url]} busy={!!busy} />
              ))}
            </tbody>
          </table>
          <div className="su-card-row">
            <Button size="sm" variant="primary" disabled={!count || !!busy} onClick={() => void addTicked()} data-testid="setup-ollama-add"
                    title="Write the ticked servers as ollama.hosts entries (an existing host is never repointed; the first host stays the default)">
              {busy === "add" ? "Adding..." : `Add the ticked${count ? ` (${count})` : ""}`}
            </Button>
          </div>
        </>
      )}
      <CardLines card="ollama-found" />
      <OllamaMeasure />
    </div>
  );
}
