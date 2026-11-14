// setup-model (3.3.0.0 R1): the default model -- the Models panel's rows for
// the providers set up here (studio/model.py model_rows: the catalog, the
// best-at line), grouped by provider, a search box over ref, name and best
// at, the saved one checked; Save writes `model` in ~/.halo/config.json, the
// model a new session starts on (`halo --model` and /model still pick
// another for one run). 3.3.0.0 R3: the rows are the cached catalog (reading
// this page probes no host); a configured Ollama host nothing has read yet
// says "not read yet: Refresh", and Refresh reads every provider's list
// (POST models/refresh, the Models panel's Refresh), then the page again.
// 3.3.5.0 R0 (f): every model is drawn (lib/ui/WindowedRows past 200 rows), a
// count line says how many, a provider group folds with its chevron (kept per
// browser), and Refresh answers on its own line, never in a toast; (e) a
// local row carries its effort word (think on/off, effort n/a). 3.3.5.0 R0b:
// each row carries its card's chips and the fit meter; the model picked shows
// its card under the list, and when it cannot orchestrate here the one line
// with the coder-lane offer (shared/ModelCard.tsx). 3.3.15.0 R2 (owner feedback
// 2026-11-09): a row is one line -- ref, label, what it takes (shared/
// ModelTakes.tsx tags, the honest line on hover), price, context and meter;
// the picked row's line, effort word and card chips sit on one line under the list. 3.4.1.3 ("Pick, don't type"): the
// list is THE picker (shared/picker/ModelPicker.tsx) over these cached rows, its Setup test ids kept (setup-model-*).
import { useMemo, useState } from "react";
import { api } from "../../lib/api";
import { Button, Empty } from "../../lib/ui";
import { loadModels } from "../roles/sync";
import type { ModelRow as CatalogRow } from "../roles/types";
import { CardChips, ModelCardPanel } from "../shared/ModelCard";
import { ModelPicker } from "../shared/picker/ModelPicker";
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { loadSetup, NONE, pick, shownOf, useSetup, type ModelRow } from "./store";

const FOLD_KEY = "halo.setup.model.folded";

/** Setup's cached rows (reading this page probes no host) in the picker's row shape. */
function asCatalog(r: ModelRow): CatalogRow {
  return { ref: r.ref, provider: r.provider, group: "", detail: r.label, price_in: null, price_out: null, price: r.price, context: r.context,
    context_tokens: null, speed: "", local: r.provider === "ollama", chips: "", best_at: { line: r.best_at, kinds: [] }, takes: r.takes,
    effort_word: r.effort, card: r.card, fit: r.fit };
}

function Refresh() {
  const notes = useSetup((s) => s.data?.model_notes || NONE);
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState<{ ok: boolean; text: string } | null>(null);
  const go = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ rows?: number }>("models/refresh", {});
      setSaid({ ok: true, text: `the catalog read again: ${r.rows ?? 0} models` });
      void loadModels();
    } catch (e) {
      setSaid({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
      void loadSetup();
    }
  };
  return (
    <div className="su-card-row">
      {notes.map((n) => (
        <span key={n} className="su-note muted" data-testid="setup-model-note">{n}</span>
      ))}
      <Button size="sm" variant="ghost" disabled={busy} onClick={() => void go()} title="halo models --refresh" data-testid="setup-model-refresh">
        {busy ? "Reading..." : "Refresh"}
      </Button>
      {said && <span className="su-note mono" data-ok={said.ok || undefined} data-testid="setup-model-refreshed">{said.text}</span>}
    </div>
  );
}

export function DefaultModelDetail() {
  const { ready, error } = useLoadState();
  const rows = useSetup((s) => s.data?.models || NONE);
  const shown = useSetup((s) => shownOf(s, "model"));
  const saved = useSetup((s) => s.data?.model || "");
  const list = useMemo(() => rows.map(asCatalog), [rows]);
  const known = rows.some((r) => r.ref === saved);
  const picked = rows.find((r) => r.ref === shown); // 3.3.15.0 R2: its honest line, effort word and card chips, one line
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-default-model">
      <p className="su-lead muted">
        The model a new session starts on. {saved ? <>Saved: <b className="mono" data-testid="setup-model-saved">{saved}</b>{known ? "" : " (not in the catalog of the providers set up here)"}.</> : "Nothing saved yet."}
      </p>
      <Refresh />
      {rows.length === 0 ? (
        <Empty title="No model to pick yet" testid="setup-models-empty"
               body="The list is the catalog of the providers set up here. Set a provider up first (the Providers block), then Refresh." />
      ) : (
        <ModelPicker value={shown} onPick={(ref) => ref && pick("model", ref)} rows={list} tid="setup-model" foldKey={FOLD_KEY} embedded />
      )}
      {picked && (
        <div className="su-model-detail mono" data-testid="setup-model-line" data-ref={picked.ref} title={picked.best_at || undefined}>
          {picked.ref}: {picked.best_at || "?"}{" "}
          {picked.effort ? <span className="og-chip mono" data-testid="setup-model-effort" title="what the effort level does on this model">{picked.effort}</span> : null}
          <CardChips card={picked.card} />
        </div>
      )}
      {shown ? <ModelCardPanel refName={shown} onLane={() => void loadSetup()} /> : null}
      <BlockFoot block="model" what="halo config set model <ref>" />
    </div>
  );
}

export function DefaultModelGlance() {
  const saved = useSetup((s) => s.data?.model || "");
  const n = useSetup((s) => s.data?.models.length || 0);
  return (
    <div className="glance">
      <div className="glance-kicker mono">DEFAULT MODEL</div>
      <div className="glance-text">{saved || "not set"}</div>
      <div className="glance-hint">{n} model{n === 1 ? "" : "s"} in the catalog</div>
    </div>
  );
}
