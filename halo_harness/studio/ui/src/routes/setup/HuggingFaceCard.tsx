// The Hugging Face card in Setup's Providers block (3.3.0.0 R2): the wizard's
// three sources, each on its own: the router token (HF_TOKEN in the env
// file), dedicated endpoints (`huggingface.endpoints`) and local servers
// (`huggingface.local_servers`) as tables with add and remove; a token for an
// endpoint or a server goes to the env file and config.json keeps its
// variable name. A server that is not added here is still found on its own.
import { CardHead } from "./ProviderCard";
import { CardLines, MiniForm, send, Table } from "./cards";
import { NONE, useSetup, type ProviderInfo } from "./store";

const ENDPOINT = [
  { id: "name", label: "Endpoint name" },
  { id: "url", label: "Endpoint URL", placeholder: "the endpoint's https URL" },
  { id: "token", label: "Token (optional)", secret: true },
];
const SERVER = [
  { id: "name", label: "Server name", placeholder: "blank = default" },
  { id: "url", label: "Server URL", placeholder: "127.0.0.1:8080" },
  { id: "api_key", label: "API key (optional)", secret: true },
];

export function HuggingFaceCard({ p }: { p: ProviderInfo }) {
  const hf = useSetup((s) => s.data?.huggingface);
  const endpoints = hf?.endpoints || NONE;
  const servers = hf?.local_servers || NONE;
  const parts = [endpoints.length && `${endpoints.length} endpoint${endpoints.length === 1 ? "" : "s"}`,
    servers.length && `${servers.length} local server${servers.length === 1 ? "" : "s"}`].filter(Boolean).join(", ");
  return (
    <section className="su-card" data-testid="setup-provider" data-name="huggingface" data-set={p.set || undefined}>
      <CardHead name="huggingface" p={p} extra={parts} />
      <div className="su-sub mono">Router token {hf?.token_set ? <span className="su-on">set{p.tail ? `, ${p.tail}` : ""}</span> : <span className="muted">not set</span>}</div>
      <MiniForm card="hf-token" inputs={[{ id: "token", label: "HF_TOKEN", secret: true, placeholder: hf?.token_set ? "paste a token to replace it" : "paste a token" }]}
                button="Save & test" onSave={(v) => send("hf-token", "setup/hf", { token: v.token || "" })} />
      <CardLines card="hf-token" />
      <div className="su-sub mono">Dedicated endpoints</div>
      <Table card="hf-endpoint" head={["name", "url", "token env"]} rows={endpoints.map((e) => ({ key: e.name, cells: [e.name, e.url, e.token_env || "-"] }))}
             onRemove={(name) => void send("hf-endpoint", "setup/hf", { remove_endpoint: name })} />
      <MiniForm card="hf-endpoint" inputs={ENDPOINT} button="Add endpoint & test"
                onSave={(v) => send("hf-endpoint", "setup/hf", { endpoint: { name: v.name || "", url: v.url || "", token: v.token || "" } })} />
      <CardLines card="hf-endpoint" />
      <div className="su-sub mono">Local servers</div>
      <Table card="hf-local" head={["name", "url", "key env"]} rows={servers.map((e) => ({ key: e.name, cells: [e.name, e.url, e.key_env || "-"] }))}
             onRemove={(name) => void send("hf-local", "setup/hf", { remove_local_server: name })} />
      <MiniForm card="hf-local" inputs={SERVER} button="Add server & test"
                onSave={(v) => send("hf-local", "setup/hf", { local_server: { name: v.name || "", url: v.url || "", api_key: v.api_key || "" } })} />
      <CardLines card="hf-local" />
    </section>
  );
}
