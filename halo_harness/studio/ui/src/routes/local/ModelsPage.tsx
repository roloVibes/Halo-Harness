// Local -> Models (3.3.5.0 R1): per host every installed model (Ollama's
// /api/tags with /api/show, a Hugging Face local server's /v1/models) as a row
// (ModelRow.tsx). On top the intent filter (idea 3, intents not model names):
// code, chat, read long documents, look at images, embed -- the rows ranked by
// their fit for this card and that intent (studio/local_models_view.py scores
// each row: the card's purpose and roles decide the band, the fit meter the
// place in it), a model that is not for the intent left out, and one line under
// it saying why this order. The Fleet Ollama panel's rows link here. 3.3.5.0 R3: the Loaded-now strip on top
// (LoadedNow.tsx: what each host has in memory, its VRAM share, when it unloads, Unload), the Jobs list, and the
// card a row's actions menu opens (ModelCards.tsx).
import { useEffect, useMemo, useState } from "react";
import { Empty } from "../../lib/ui";
import { LoadedNow } from "./LoadedNow";
import { ModelActCard } from "./ModelCards";
import { ModelRow } from "./ModelRow";
import { JobsList } from "./Pulls";
import { goto, pages } from "./pages";
import { loadModels, useLocal } from "./store";
import { useStore } from "../../lib/store";
import type { ModelEntry } from "./types";

function rank(rows: ModelEntry[], intent: string): ModelEntry[] {
  if (!intent) return rows;
  return rows.filter((r) => r.intent?.[intent] != null).sort((a, b) => (b.intent[intent] as number) - (a.intent[intent] as number) || a.model.localeCompare(b.model));
}

export function ModelsPage() {
  const data = useLocal((s) => s.models);
  const error = useLocal((s) => s.error);
  const only = useStore(pages, (s) => s.host);
  const [intent, setIntent] = useState("");
  useEffect(() => {
    void loadModels();
  }, []);
  const hosts = useMemo(() => (data?.hosts || []).filter((h) => !only || h.name === only), [data, only]);
  if (!data) return error ? <Empty title="Studio could not read the models" body={error} /> : <div className="mono muted">reading the models...</div>;
  const why = data.intents.find((i) => i.id === intent)?.why || "";
  return (
    <div className="lc-models" data-testid="local-models">
      <LoadedNow hosts={hosts} />
      <JobsList />
      <ModelActCard />
      <div className="lc-intents" role="group" aria-label="What do you want a model for" data-testid="local-intents">
        <span className="mono muted">for:</span>
        <button type="button" className={"lc-intent" + (intent ? "" : " on")} onClick={() => setIntent("")} data-testid="local-intent" data-intent="">any</button>
        {data.intents.map((i) => (
          <button key={i.id} type="button" className={"lc-intent" + (intent === i.id ? " on" : "")} onClick={() => setIntent(i.id)}
                  data-testid="local-intent" data-intent={i.id} aria-pressed={intent === i.id}>
            {i.title}
          </button>
        ))}
        {only && (
          <button type="button" className="lc-intent" onClick={() => goto("models", "")} data-testid="local-models-all" title="every host's models">
            {only} only · show every host
          </button>
        )}
      </div>
      {why && <p className="muted lc-why" data-testid="local-intent-why">why this order: {why}</p>}
      {hosts.map((h) => {
        const rows = rank(h.models, intent);
        const left = h.models.length - rows.length;
        return (
          <section key={h.name} className="lc-block" aria-label={h.name} data-testid="local-models-host" data-host={h.name}>
            <div className="rail-label mono">{h.name.toUpperCase()} · {h.kind.toUpperCase()} · {h.models.length} MODEL{h.models.length === 1 ? "" : "S"}</div>
            {rows.length ? (
              <ul className="lc-model-list">
                {rows.map((m) => <ModelRow key={m.ref} m={m} host={h.name} score={intent ? m.intent[intent] : undefined} />)}
              </ul>
            ) : (
              <p className="muted">{h.models.length ? "None of its models is for this intent." : "No model installed here, or the server did not answer."}</p>
            )}
            {left > 0 && rows.length > 0 && <p className="muted mono">{left} not for this intent, left out</p>}
          </section>
        );
      })}
      {!hosts.length && <Empty title="No host lists a model" body="Add an Ollama host in Setup -> Providers, or a local server." testid="local-models-none" />}
    </div>
  );
}
