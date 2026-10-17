// roles-models (3.0.7.0 R2; model-notice.js in the classic page): the model
// catalog Studio picks from -- how many rows, each provider with whether it
// is enabled, has a key and how many models it has cached, and, when the
// catalog is empty, why -- and Refresh (`POST models/refresh`: every
// enabled provider's list again). "Test this model" runs the probe on any
// ref you type here.
import { useEffect, useState } from "react";
import { Button } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { refreshModels } from "./bioActions";
import { TestButton } from "./ModelPicker";
import { useRoles } from "./store";
import { loadModelsStatus } from "./sync";

export function ModelsDetail() {
  const st = useRoles((s) => s.modelsStatus);
  const rows = useRoles((s) => s.models.length);
  const busy = useRoles((s) => s.busy === "refresh");
  const [ref, setRef] = useState("");
  useEffect(() => void loadModelsStatus(), []);
  return (
    <div className="rmo" data-testid="roles-models-body">
      <div className="rlu-bar">
        <span className="mono"><b data-testid="roles-models-count">{rows}</b> models in the catalog</span>
        <span className="spacer" />
        <Button size="sm" variant={rows ? "default" : "primary"} disabled={busy} onClick={() => void refreshModels()} data-testid="roles-models-refresh">
          {busy ? "Refreshing..." : "Refresh"}
        </Button>
      </div>
      {st?.reason && <p className="rmo-why" data-testid="roles-models-why">{st.reason}</p>}
      {st ? (
        <ul className="rmo-list">
          {st.providers.filter((p) => p.enabled || p.credentials).map((p) => (
            <li key={p.name} className="oco-row" data-ok={p.enabled && (p.model_count || 0) > 0}>
              <span className="oco-dot" aria-hidden="true" />
              <span className="rail-label mono">{p.label}</span>
              <span className="mono muted">{p.status}{typeof p.model_count === "number" ? ` · ${p.model_count} cached` : ""}{p.enabled ? "" : " · not enabled"}</span>
            </li>
          ))}
          {!st.providers.some((p) => p.enabled || p.credentials) && <li className="muted">No provider is set up here yet: halo init (the keys step), then Refresh.</li>}
        </ul>
      ) : (
        <div className="og-wait mono muted">asking the providers...</div>
      )}
      <div className="field re-field">
        <span className="field-label mono">Test a model</span>
        <input className="input mono" value={ref} placeholder="or:vendor/model, ol:qwen3:30b..." onChange={(e) => setRef(e.target.value)} aria-label="A model ref to test" data-testid="roles-models-ref" />
        <TestButton value={ref.trim()} />
      </div>
    </div>
  );
}

export function ModelsGlance() {
  const rows = useRoles((s) => s.models.length);
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={rows} label="models" tone={rows ? undefined : "warn"} />
      </div>
      <div className="glance-hint">{rows ? "Expand for the providers and Refresh." : "The catalog is empty: expand to see why."}</div>
    </div>
  );
}
