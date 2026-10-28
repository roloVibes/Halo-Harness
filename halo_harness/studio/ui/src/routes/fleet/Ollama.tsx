// fleet-ollama (3.3.4.0 R5): the Ollama steward's panel. Optional (the header's "+" adds it; the attention
// row of kind `ollama_steward` and the palette's "Fleet: Ollama" open it), a strip in the full arrangement.
// Per host (a picker when there is more than one; a Hugging Face local server is one too): the card line (the
// GPUs and their free memory, the server's own settings, what else holds the card), the models table
// (OllamaModels.tsx), the traffic timeline and the fit plan (OllamaPlan.tsx), and the steward block
// (OllamaSteward.tsx). Live through the job's `steward` frames, and a refetch every 30 s while it is open
// (a job in another process sends no frames). Nothing here calls a model or writes to a server.
import { useEffect } from "react";
import { goSection } from "../../lib/store";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { layoutStore, showPanel } from "../../lib/workspace/persist";
import { Empty } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { HELP } from "../help";
import { ModelsTable } from "./OllamaModels";
import { PlanBlock, Timeline } from "./OllamaPlan";
import { StewardBlock } from "./OllamaSteward";
import { loadAll, pickHost, REFRESH_MS, startOllamaFeed, useOllama, type HostView } from "./ostore";
import { enterWorkspace } from "./store";

function useOllamaData(): void {
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

const CARD = /^(GPU |memory: |server |other: )/;

function CardLine({ h }: { h: HostView }) {
  if (h.kind === "local server") return <p className="mono muted oll-card" data-testid="ollama-card">{h.url} · an OpenAI-dialect local server: its window and reply rules apply</p>;
  const lines = h.card_lines.filter((l) => CARD.test(l));
  return (
    <div className="oll-card mono" data-testid="ollama-card" title={h.card_lines.join("\n")}>
      {lines.length ? lines.map((l) => <div key={l}>{l}</div>) : <span className="muted">card not read: {h.url}</span>}
    </div>
  );
}

export function OllamaDetail() {
  useOllamaData();
  const data = useOllama((s) => s.hosts);
  const error = useOllama((s) => s.error);
  const pick = useOllama((s) => s.host);
  const buckets = useOllama((s) => s.timeline[s.host]);
  if (!data) return error ? <Empty title="Studio could not read the steward" body={error} /> : <div className="og-wait mono muted">reading the hosts...</div>;
  const all = [...data.hosts, ...data.local_servers];
  const h = all.find((x) => x.name === pick) || all[0];
  if (!h) return <Empty title="No Ollama host is configured" body="Add one in Settings → Ollama (ollama.hosts), or Setup → Providers finds the servers on this network." testid="ollama-none" />;
  return (
    <div className="oll" data-testid="fleet-ollama-detail" data-host={h.name}>
      <div className="oll-bar">
        <Picker all={all} host={h.name} />
        <b className="mono">{h.name}</b>
        <span className="mono muted">{h.kind === "local server" ? "local server" : h.served_here ? "served here" : h.url}</span>
      </div>
      <CardLine h={h} />
      <ModelsTable host={h} />
      <Timeline buckets={buckets} />
      <StewardBlock findings={h.findings} />
      <PlanBlock plan={h.plan} />
    </div>
  );
}

export function OllamaGlance() {
  useOllamaData();
  const data = useOllama((s) => s.hosts);
  const note = useOllama((s) => s.steward?.last_note);
  const found = (data?.hosts || []).reduce((n, h) => n + h.findings.filter((f) => !f.applied).length, 0);
  const calls = (data?.hosts || []).reduce((n, h) => n + h.models.reduce((m, r) => m + (r.hour?.calls || 0), 0), 0);
  return (
    <div className="glance" data-testid="fleet-ollama-glance">
      <div className="glance-numbers">
        <Metric value={data ? calls : "..."} label="calls this hour" />
        <Metric value={found} label="findings" tone={found ? "warn" : undefined} />
      </div>
      <div className="glance-hint mono">{note?.say || "no note yet"}</div>
    </div>
  );
}

export function useOllamaMotion(): MotionState {
  const data = useOllama((s) => s.hosts);
  if (!data) return "none";
  const open = data.hosts.flatMap((h) => h.findings).filter((f) => !f.applied);
  if (open.some((f) => f.severity === "error")) return "error";
  return open.length ? "waiting" : "idle";
}

/** The panel (Fleet.tsx lists it after the Tree): optional, a strip in the full arrangement. */
export const ollamaPanel: PanelSpec = {
  id: "fleet-ollama", testid: "fleet-ollama", ...HELP["fleet-ollama"], title: "Ollama", x: 18, y: 0, w: 6, h: 40, minW: 6, minH: 16,
  face: "detail", optional: true, collapsed: true, glance: OllamaGlance, detail: OllamaDetail, useMotion: useOllamaMotion,
};

/** Fleet on its Ollama panel (added when it is not on the page): the attention row's O, the palette, Settings, Setup. */
export function openOllama(): void {
  goSection("fleet");
  enterWorkspace();
  const go = (tries: number) => {
    if (layoutStore("fleet").get().layout) showPanel("fleet", ollamaPanel);
    else if (tries > 0) window.setTimeout(() => go(tries - 1), 150); // the workspace mounts its layout first
  };
  go(20);
}
