// The Ollama card in Setup's Providers block (3.3.0.0 R2): the hosts in
// `ollama.hosts` as a table (name, url, default, the env variable its key is
// kept under), add one (the wizard's Ollama tab Save: a same-name save keeps
// the host's tuning, a blank save never repoints a host, the first host is the
// default; a key goes to the env file, config.json keeps its variable name),
// remove one. 3.3.0.0 R5: under it the finders (OllamaFound.tsx): Find Ollama
// servers on this machine, Scan this network, a tick per server found, Add the
// ticked, then Measure the found models (OllamaMeasure.tsx). 3.3.1.0 R1: the
// finders sit in a disclosure under the hosts, closed until opened. 3.3.4.0 R5: the steward's line
// (StewardLine.tsx): its last note's first line and a link to Fleet's Ollama panel.
import { CardHead } from "./ProviderCard";
import { CardLines, MiniForm, send, Table } from "./cards";
import { useDiscover } from "./discover";
import { OllamaFound } from "./OllamaFound";
import { StewardLine } from "./StewardLine";
import { NONE, useSetup, type ProviderInfo } from "./store";

const INPUTS = [
  { id: "name", label: "Host name", placeholder: "blank = default" },
  { id: "url", label: "Ollama URL", placeholder: "blank = 127.0.0.1:11434" },
  { id: "api_key", label: "API key (optional)", secret: true, placeholder: "paste a key (Ollama Cloud)" },
];

export function OllamaCard({ p }: { p: ProviderInfo }) {
  const hosts = useSetup((s) => s.data?.ollama.hosts || NONE);
  const rows = hosts.map((h) => ({ key: h.name, cells: [h.name, h.url, h.default ? "default" : "", h.key_env || "-"] }));
  const wide = useDiscover((s) => s.rows.length > 0 || !!s.measure?.job); // the found table takes the whole row
  return (
    <section className="su-card" data-testid="setup-provider" data-name="ollama" data-set={p.set || undefined}
             style={wide ? { gridColumn: "1 / -1" } : undefined}>
      <CardHead name="ollama" p={p} extra={hosts.length ? `${hosts.length} host${hosts.length === 1 ? "" : "s"}` : ""} />
      <Table card="ollama" head={["name", "url", "default", "key env"]} rows={rows}
             onRemove={(name) => void send("ollama", "setup/ollama-host/remove", { name })} />
      <MiniForm card="ollama" inputs={INPUTS} button="Add host & test" allowBlank
                title="every field blank registers the local daemon (127.0.0.1:11434) when no host is set"
                onSave={(v) => send("ollama", "setup/ollama-host", { name: v.name || "", url: v.url || "", api_key: v.api_key || "" })} />
      <CardLines card="ollama" />
      <StewardLine />
      <details className="su-more-box" data-testid="setup-ollama-more">
        <summary className="mono">Find, scan, add and measure Ollama servers</summary>
        <OllamaFound />
      </details>
    </section>
  );
}
