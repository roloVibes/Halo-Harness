// The Ollama card in Setup's Providers block (3.3.0.0 R2): the hosts in
// `ollama.hosts` as a table (name, url, default, the env variable its key is
// kept under), add one (the wizard's Ollama tab Save: a same-name save keeps
// the host's tuning, a blank save never repoints a host, the first host is the
// default; a key goes to the env file, config.json keeps its variable name),
// remove one. Finding Ollama servers on this machine and on the network comes
// with 3.3.0.0 R5 (`halo ollama discover` does it from a terminal).
import { Button } from "../../lib/ui";
import { CardHead } from "./ProviderCard";
import { CardLines, MiniForm, send, Table } from "./cards";
import { NONE, useSetup, type ProviderInfo } from "./store";

const INPUTS = [
  { id: "name", label: "Host name", placeholder: "blank = default" },
  { id: "url", label: "Ollama URL", placeholder: "blank = 127.0.0.1:11434" },
  { id: "api_key", label: "API key (optional)", secret: true, placeholder: "paste a key (Ollama Cloud)" },
];

export function OllamaCard({ p }: { p: ProviderInfo }) {
  const hosts = useSetup((s) => s.data?.ollama.hosts || NONE);
  const rows = hosts.map((h) => ({ key: h.name, cells: [h.name, h.url, h.default ? "default" : "", h.key_env || "-"] }));
  return (
    <section className="su-card" data-testid="setup-provider" data-name="ollama" data-set={p.set || undefined}>
      <CardHead name="ollama" p={p} extra={hosts.length ? `${hosts.length} host${hosts.length === 1 ? "" : "s"}` : ""} />
      <Table card="ollama" head={["name", "url", "default", "key env"]} rows={rows}
             onRemove={(name) => void send("ollama", "setup/ollama-host/remove", { name })} />
      <MiniForm card="ollama" inputs={INPUTS} button="Add host & test" allowBlank
                title="every field blank registers the local daemon (127.0.0.1:11434) when no host is set"
                onSave={(v) => send("ollama", "setup/ollama-host", { name: v.name || "", url: v.url || "", api_key: v.api_key || "" })} />
      <div className="su-card-row">
        <Button size="sm" disabled data-testid="setup-ollama-find">Find Ollama servers</Button>
        <Button size="sm" disabled data-testid="setup-ollama-scan">Scan this network</Button>
        <span className="su-note muted" data-testid="setup-ollama-later">comes with 3.3.0.0 R5 (until then: halo ollama discover)</span>
      </div>
      <CardLines card="ollama" />
    </section>
  );
}
