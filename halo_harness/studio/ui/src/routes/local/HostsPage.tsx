// Local -> Hosts (3.3.5.0 R1): every host Halo knows as a card (HostCard.tsx) --
// the ollama.hosts entries, the Hugging Face local servers, the hosts fleet
// members serve (their samples reach this hub: idea 5), and the servers Find or
// Scan found that are not configured yet (with Add to hosts). GET local/hosts,
// again every 30 s while the page is open and when config.json moves; the
// models' fit meters come from GET local/models. 3.3.7.0 R1: a machine a paired halo host serves is grouped first,
// under SERVED BY HALO HOST (its card says so: HostServedBy.tsx).
import { useEffect, useMemo } from "react";
import { Empty } from "../../lib/ui";
import type { Fit } from "../../lib/ui/FitMeter";
import { HfCards } from "./HfCards";
import { HostCard } from "./HostCard";
import { HostPending } from "./HostPending";
import { loadHosts, loadModels, useLocal } from "./store";

const REFRESH_MS = 30_000;
const ORDER = ["host", "configured", "managed server", "local server", "member", "discovered"];
const GROUP: Record<string, string> = {
  host: "SERVED BY HALO HOST", configured: "CONFIGURED · OLLAMA.HOSTS", "managed server": "LOCAL SERVERS · STARTED BY HALO",
  "local server": "LOCAL SERVERS · HUGGINGFACE.LOCAL_SERVERS",
  member: "SERVED BY FLEET MEMBERS", discovered: "FOUND, NOT ADDED",
};

export function HostsPage() {
  const hosts = useLocal((s) => s.hosts);
  const models = useLocal((s) => s.models);
  const error = useLocal((s) => s.error);
  useEffect(() => {
    void loadHosts();
    void loadModels();
    const id = window.setInterval(() => {
      if (!document.hidden) void loadHosts();
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);
  const fits = useMemo(() => {
    const out: Record<string, Record<string, Fit>> = {};
    for (const h of models?.hosts || []) out[h.name] = Object.fromEntries(h.models.map((m) => [m.model, m.fit]));
    return out;
  }, [models]);
  if (!hosts) return error ? <Empty title="Studio could not read the hosts" body={error} /> : <div className="mono muted">reading the hosts...</div>;
  if (!hosts.length)
    return <Empty title="No host yet" body="Add one in Setup -> Providers -> Ollama, or Find the servers on this machine there." testid="local-hosts-none" />;
  return (
    <div className="lc-hosts" data-testid="local-hosts">
      <HostPending />
      {ORDER.map((src) => {
        const rows = hosts.filter((h) => (h.host ? "host" : h.source) === src);
        if (!rows.length) return null;
        return (
          <section key={src} className="lc-block" aria-label={GROUP[src]} data-testid="local-hosts-group" data-source={src}>
            <div className="rail-label mono">{GROUP[src]}</div>
            <div className="lc-host-grid">
              {rows.map((h) => <HostCard key={`${h.source}|${h.name}`} h={h} fits={fits[h.name] || {}} />)}
            </div>
          </section>
        );
      })}
      <HfCards />
    </div>
  );
}
