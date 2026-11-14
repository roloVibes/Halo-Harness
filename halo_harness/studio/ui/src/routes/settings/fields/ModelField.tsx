// A model row's control (3.3.5.0 R0 (f); 3.4.1.3 "Pick, don't type"): the one model field (shared/ModelSelect.tsx)
// over THE picker -- the models of the providers set up here, searchable, one line each with what it takes and the fit
// meter -- never a text box. Its first row keeps the default (the key unset: a pick of it is Reset); a saved value the
// catalog lacks shows marked "not in your catalog". `bare` (embeddings.model): the value is an Ollama model's own name,
// so the picker lists the Ollama models only and saves the name without `ol:`. On the `model` row (`main`) the saved
// model's card shows under it, with the coder-lane offer when it cannot orchestrate here (shared/ModelCard.tsx).
import { ModelCardPanel } from "../../shared/ModelCard";
import { ModelSelect } from "../../shared/ModelSelect";
import type { ModelRow } from "../../roles/types";
import { loadValues } from "../store";

const ollamaOnly = (m: ModelRow) => m.provider === "ollama" || m.ref.startsWith("ol:");
const text = (v: unknown) => (typeof v === "string" ? v : v === null || v === undefined ? "" : JSON.stringify(v));

export function ModelField({ value, fallback, label, disabled, onSave, onReset, main, bare }: {
  id?: string;
  value: unknown;
  fallback: unknown;
  label: string;
  disabled?: boolean;
  onSave: (v: string) => void;
  onReset: () => void;
  main?: boolean;
  bare?: boolean;
}) {
  const saved = text(value);
  const shown = bare && saved && !saved.startsWith("ol:") ? `ol:${saved}` : saved;
  const dflt = text(fallback);
  const pick = (ref: string) => {
    if (!ref) return onReset();
    onSave(bare ? ref.replace(/^ol:/, "").replace(/@.*$/, "") : ref);
  };
  return (
    <div className="st-model" data-testid="settings-model">
      <ModelSelect label={label} value={shown} onPick={pick} testid="settings-model-field" busy={disabled} inline bare compact
                   inherit={{ label: "the default", model: dflt }} only={bare ? ollamaOnly : undefined} onlyWhat="Ollama model" noTest={bare} tid="settings-model" />
      {main && saved ? <ModelCardPanel refName={saved} onLane={() => void loadValues()} /> : null}
    </div>
  );
}
