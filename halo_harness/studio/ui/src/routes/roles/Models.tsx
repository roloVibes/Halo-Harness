// roles-models (3.0.7.0 R2; model-notice.js in the classic page): the model
// catalog Studio picks from -- how many rows, each provider with whether it
// is enabled, has a key and how many models it has cached, and, when the
// catalog is empty, why -- and Refresh (`POST models/refresh`: every
// enabled provider's list again). "Test this model" runs the probe on any
// ref you type here. 3.1.4.0 R4: the reason names every provider looked at
// and why it lists nothing; under it, when the last Refresh ran and each
// provider's outcome (shared/catalog.tsx, the lines every model select shows).
// 3.1.9.0 R1: Analyze (`POST models/analyze`, what `halo models analyze`
// does) rebuilds what each model is good at; the counts per kind and each
// kind's strongest model show under the bar, and the picker's "best at"
// column follows.
import { useEffect, useState } from "react";
import { Button } from "../../lib/ui";
import { Metric } from "../orchestra/bits";
import { CatalogLines } from "../shared/catalog";
import { analyzeModels, refreshModels } from "./bioActions";
import { TestButton } from "./ModelPicker";
import { useRoles } from "./store";
import { loadModelsStatus } from "./sync";

function AnalysisLine() {
  const a = useRoles((s) => s.analysis);
  if (!a) return null;
  const kinds = Object.entries(a.kinds);
  return (
    <div className="rmo-analysis mono" data-testid="roles-models-analysis">
      <div><b>{a.rows}</b> models analyzed{kinds.length ? ": " + kinds.map(([k, n]) => `${k} ${n}`).join(" · ") : ": no kind stated by the catalog"}</div>
      {Object.entries(a.best).map(([k, b]) => (
        <div key={k} className="muted" data-kind={k}>{k}: {b.strongest}{b.cheapest && b.cheapest !== b.strongest ? ` · cheapest ${b.cheapest}` : ""}</div>
      ))}
    </div>
  );
}

export function ModelsDetail() {
  const st = useRoles((s) => s.modelsStatus);
  const rows = useRoles((s) => s.models.length);
  const busy = useRoles((s) => s.busy);
  const [ref, setRef] = useState("");
  useEffect(() => void loadModelsStatus(), []);
  return (
    <div className="rmo" data-testid="roles-models-body">
      <div className="rlu-bar">
        <span className="mono"><b data-testid="roles-models-count">{rows}</b> models in the catalog</span>
        <span className="spacer" />
        <Button size="sm" variant="ghost" disabled={busy === "analyze" || !rows} onClick={() => void analyzeModels()} data-testid="roles-models-analyze"
                title="Rebuild what each model is good at from the catalog and what this machine measured (halo models analyze)">
          {busy === "analyze" ? "Analyzing..." : "Analyze"}
        </Button>
        <Button size="sm" variant={rows ? "default" : "primary"} disabled={busy === "refresh"} onClick={() => void refreshModels()} data-testid="roles-models-refresh">
          {busy === "refresh" ? "Refreshing..." : "Refresh"}
        </Button>
      </div>
      <AnalysisLine />
      {st?.reason && <p className="rmo-why" data-testid="roles-models-why">{st.reason}</p>}
      <CatalogLines empty={false} />
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
      <div className="glance-hint">{rows ? "Expand for the providers, Analyze and Refresh." : "The catalog is empty: expand to see why."}</div>
    </div>
  );
}
