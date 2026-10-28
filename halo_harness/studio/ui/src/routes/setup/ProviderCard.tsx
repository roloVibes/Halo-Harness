// One provider's card in Setup's Providers block (3.3.0.0 R2): the state line
// ("set, from the env file, ****1234" or "not set"; 3.3.5.0 R0 (g): per field,
// "host from Claude Code's settings.json · token not set"), the enabled mark, what
// the last test found, one field per variable the wizard's tab asks for (a
// key is a password field, never prefilled) and Save & test, which writes
// the variables to the env file through the wizard's own writer, enables the
// provider, probes it and refreshes its catalog (studio/setup_providers_api.py).
import type { ProviderInfo } from "./store";
import { CardLines, MiniForm, send, type Input } from "./cards";

const FROM: Record<string, string> = { "env file": "from the env file", environment: "from the environment", "typed here": "typed here" };
const fromWords = (src: string) => FROM[src] || `from ${src}`;

/** 3.3.5.0 R0 (g): one phrase per field, naming where its value came from -- "host from Claude Code's
 * settings.json · token not set", "host from the env file · token set (****1234)", "key set (****3344), typed
 * here" -- and never a host value beside "not set". */
function fieldLine(p: ProviderInfo): string {
  const src = p.field_sources || {};
  const others = p.fields.filter((f) => !f.secret).map((f) => src[f.id] || "");
  const parts = p.fields.map((f) => {
    const from = src[f.id] || "";
    const said = from && !others.includes(from) ? `, ${fromWords(from)}` : "";
    if (f.secret) return from || f.present ? `${f.id} set${p.tail ? ` (${p.tail})` : ""}${said}` : `${f.id} not set`;
    return from ? `${f.id} ${fromWords(from)}` : `${f.id} not set`;
  });
  return parts.join(" · ");
}

/** The card's state line: per field where a provider has typed fields with a known source; else "set, from the env file, ****1234" / "not set". */
export function stateLine(p: ProviderInfo): string {
  const src = p.field_sources || {};
  if (p.fields.length && Object.values(src).some(Boolean)) return fieldLine(p);
  if (!p.set) return "not set";
  const from = p.source === "env file" ? "from the env file" : `from ${p.source === "environment" ? "the environment" : p.source}`;
  return ["set", from, p.tail].filter(Boolean).join(", ");
}

/** "reachable: ok · 312 models listed" (what the last Save & test found; "not checked" before one). */
export function testLine(p: ProviderInfo): string {
  const n = p.catalog_count;
  return `reachable: ${p.reachable}` + (n ? ` · ${n} model${n === 1 ? "" : "s"} listed` : "");
}

export function CardHead({ name, p, extra }: { name: string; p: ProviderInfo; extra?: string }) {
  return (
    <div className="su-card-head">
      <span className="su-card-title">{p.label}</span>
      <span className="su-mark mono" data-on={p.enabled || undefined} data-testid="setup-provider-enabled" data-name={name}
            title={p.enabled ? "enabled: its models are listed and used" : p.set ? "set but turned off (halo providers enable " + name + ")" : "not set up"}>
        {p.enabled ? "enabled" : p.set ? "off" : "-"}
      </span>
      <span className="su-card-state mono" data-set={p.set || undefined} data-testid="setup-provider-state" data-name={name}>
        {stateLine(p)}
        {extra ? ` · ${extra}` : ""}
      </span>
      <span className="su-card-test mono muted" data-testid="setup-provider-test" data-name={name}>
        {testLine(p)}
      </span>
    </div>
  );
}

function inputs(name: string, p: ProviderInfo): Input[] {
  return p.fields.map((f) => {
    if (f.secret) return { id: f.id, label: f.label, secret: true, placeholder: f.present ? `paste a key to replace ${p.tail || "the one set"}` : "paste a key" };
    if (name === "databricks" && f.id === "host") {
      const placeholder = p.host_hint ? `retype ${p.host_hint} to use it` : p.detail || f.placeholder || "";
      return { id: f.id, label: f.label, placeholder };
    }
    return { id: f.id, label: f.label, placeholder: f.placeholder || "" };
  });
}

export function ProviderCard({ name, p }: { name: string; p: ProviderInfo }) {
  return (
    <section className="su-card" data-testid="setup-provider" data-name={name} data-set={p.set || undefined}>
      <CardHead name={name} p={p} />
      <MiniForm card={name} inputs={inputs(name, p)} button="Save & test" title={`writes ${p.fields.map((f) => f.label).join(", ")} to the env file`}
                onSave={(values) => send(name, `setup/provider/${name}`, { fields: values })} />
      <CardLines card={name} />
    </section>
  );
}
