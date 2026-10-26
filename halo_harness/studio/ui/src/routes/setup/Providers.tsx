// setup-providers (3.3.0.0 R2): the terminal wizard's eight Providers tabs as
// cards, in its order. A key card writes its variables to the env file
// (`HALO_ENV_FILE`, else ~/.config/halo/env); the Ollama and Hugging Face
// cards add hosts, endpoints and local servers to ~/.halo/config.json. Each
// Save & test answers what it wrote and what the probe and the catalog found;
// a key is never sent back: the card says "set, from the env file, ****1234".
import { useLoadState, Waiting } from "./BlockFoot";
import { HuggingFaceCard } from "./HuggingFaceCard";
import { OllamaCard } from "./OllamaCard";
import { ProviderCard } from "./ProviderCard";
import { providersSet, useSetup } from "./store";

export function ProvidersDetail() {
  const { ready, error } = useLoadState();
  const providers = useSetup((s) => s.data?.providers);
  const envFile = useSetup((s) => s.data?.env_file || "");
  if (!ready || !providers) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-providers">
      <p className="su-lead muted">
        Paste a key and press Save & test: it is written to <span className="mono" data-testid="setup-env-file">{envFile}</span>, the
        provider is turned on, its host probed and its model list read. A key is never shown again: the card says it is set, where it
        comes from and its last four characters.
      </p>
      <div className="su-cards">
        {Object.entries(providers).map(([name, p]) =>
          name === "ollama" ? <OllamaCard key={name} p={p} /> : name === "huggingface" ? <HuggingFaceCard key={name} p={p} /> : <ProviderCard key={name} name={name} p={p} />,
        )}
      </div>
    </div>
  );
}

export function ProvidersGlance() {
  const set = useSetup((s) => providersSet(s.data).join(", "));
  const n = useSetup((s) => Object.keys(s.data?.providers || {}).length);
  return (
    <div className="glance">
      <div className="glance-kicker mono">PROVIDERS</div>
      <div className="glance-text">{set || "none set up"}</div>
      <div className="glance-hint">{n} providers: keys in the env file</div>
    </div>
  );
}
