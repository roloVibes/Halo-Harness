// Local -> Steward, the findings (3.3.8.0 R2): what the rules find on every host and every local server (llama-server,
// LM Studio, mlx_lm.server) in the last 24 hours, the Ollama panel's rows (fleet/OllamaSteward.FindingRow: Apply in
// review mode, Dismiss), a local server's runtime as a chip beside its model. GET ollama/hosts, read when the page
// opens and on Read again; nothing opens over the page.
import { useEffect, useMemo } from "react";
import { Button } from "../../lib/ui";
import { FindingRow } from "../fleet/OllamaSteward";
import { loadHosts, useOllama } from "../fleet/ostore";
import { BlockHelp } from "./LogModelRows";

const HELP = "Each finding names its host or local server and model, what the ledger and the server's own log showed, " +
  "and at most one Halo-side change (a profile field). A local server's server-side change (--ctx-size, LM Studio's " +
  "Context Length, --n-gpu-layers) is said as a line to run where it runs; Halo never changes a server.";

export function StewardFindings() {
  const hosts = useOllama((s) => s.hosts);
  const mode = useOllama((s) => s.steward?.mode || s.hosts?.mode || "");
  useEffect(() => {
    void loadHosts();
  }, []);
  const found = useMemo(() => {
    if (!hosts) return null;
    const seen = new Set<string>();
    return [...hosts.hosts, ...hosts.local_servers].flatMap((h) => h.findings || []).filter((f) => {
      if (seen.has(f.id)) return false;
      seen.add(f.id);
      return true;
    });
  }, [hosts]);
  const servers = found ? found.filter((f) => f.runtime).length : 0;
  return (
    <section className="lc-block" aria-label="The steward's findings" data-testid="local-steward-findings"
             data-count={found ? found.length : ""} data-servers={servers}>
      <div className="lg-head">
        <span className="rail-label mono">FINDINGS · HOSTS AND LOCAL SERVERS</span>
        <BlockHelp text={HELP} testid="local-steward-findings-help" />
        <span className="spacer" />
        <Button size="sm" variant="ghost" onClick={() => void loadHosts()} data-testid="local-steward-findings-read">Read again</Button>
      </div>
      {!found ? (
        <div className="mono muted">reading the findings...</div>
      ) : found.length ? (
        <ul className="oll-findings">
          {found.map((f) => (
            <FindingRow key={f.id} f={f} review={mode === "review"} />
          ))}
        </ul>
      ) : (
        <p className="muted" data-testid="local-steward-no-findings">Nothing to fix: the calls and the servers' lines look right.</p>
      )}
    </section>
  );
}
