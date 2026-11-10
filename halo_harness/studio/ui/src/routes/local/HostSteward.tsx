// Local -> Hosts, under the cards: one host's traffic and fit (3.3.16.0 R2 "the Fleet fold": a machine's models in Local;
// the Fleet Ollama panel showed it before and went): a host picker (every Ollama host and Hugging Face local server the
// steward reads; `goto("hosts", <host>)` opens it on one -- the steward's attention row's `o`, Settings' and Setup's
// links), its models table (the last hour's calls / trims / cuts / errors, the p95 prompt against the window, the
// profile and who set it, the eye, the VRAM share: HostTraffic.tsx), its traffic timeline and its fit plan (HostPlan.tsx:
// Apply, Copy the server hint). The card line is the host's card above (`ollama-card`); its findings are Local ->
// Steward's (a link here). Live through the steward's frames and a refetch every 30 s while the page is open.
import { useEffect } from "react";
import { useStore } from "../../lib/store";
import { Empty } from "../../lib/ui";
import { PlanBlock, Timeline } from "./HostPlan";
import { ModelsTable } from "./HostTraffic";
import { loadAll, pickHost, REFRESH_MS, startOllamaFeed, useOllama, type HostView } from "./ostore";
import { goto, pages } from "./pages";

function useStewardData(): void {
  useEffect(() => {
    startOllamaFeed();
    loadAll();
    const id = window.setInterval(() => {
      if (!document.hidden) loadAll();
    }, REFRESH_MS);
    return () => window.clearInterval(id);
  }, []);
}

function Picker({ all, host }: { all: HostView[]; host: string }) {
  if (all.length < 2) return null;
  return (
    <label className="oll-picker">
      <span className="mono muted">host</span>
      <select className="input mono" value={host} onChange={(e) => pickHost(e.target.value)} data-testid="ollama-host">
        {all.map((h) => (
          <option key={h.name} value={h.name}>
            {h.name}{h.kind === "local server" ? " (local server)" : h.served_here ? " (this machine)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

export function HostSteward() {
  useStewardData();
  const data = useOllama((s) => s.hosts);
  const error = useOllama((s) => s.error);
  const pick = useOllama((s) => s.host);
  const asked = useStore(pages, (s) => s.host);
  const buckets = useOllama((s) => s.timeline[s.host]);
  const all = data ? [...data.hosts, ...data.local_servers] : [];
  useEffect(() => {
    if (asked && all.some((h) => h.name === asked) && asked !== pick) pickHost(asked); // a door named the host
  }, [asked, data]);
  if (!data) return error ? <Empty title="Studio could not read the steward" body={error} /> : <div className="og-wait mono muted">reading the hosts' traffic...</div>;
  const h = all.find((x) => x.name === pick) || all[0];
  if (!h) return null;
  const open = h.findings.filter((f) => !f.applied).length;
  return (
    <section className="lc-block oll" aria-label="Traffic and fit" data-testid="local-host-steward" data-host={h.name}>
      <div className="oll-bar" data-density="bar">
        <span className="rail-label mono">TRAFFIC AND FIT</span>
        <Picker all={all} host={h.name} />
        <b className="mono">{h.name}</b>
        <span className="mono muted">{h.kind === "local server" ? "local server" : h.served_here ? "served here" : h.url}</span>
        <span className="spacer" />
        <button className="og-link mono" onClick={() => goto("steward")} data-testid="local-host-findings" title="Its findings, Apply and Dismiss: Local -> Steward">
          {open} finding{open === 1 ? "" : "s"} on Steward
        </button>
      </div>
      <ModelsTable host={h} />
      <Timeline buckets={buckets} />
      <PlanBlock plan={h.plan} />
    </section>
  );
}
