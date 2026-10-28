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
// with the coder-lane offer (shared/ModelCard.tsx).
import { useMemo, useState } from "react";
import { api } from "../../lib/api";
import { Button, Empty, FitMeter, Icon, WindowedRows } from "../../lib/ui";
import { CardChips, ModelCardPanel } from "../shared/ModelCard";
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { loadSetup, NONE, pick, shownOf, useSetup, type ModelRow } from "./store";

const FOLD_KEY = "halo.setup.model.folded";

function groups(rows: ModelRow[], q: string): [string, ModelRow[]][] {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const hit = (r: ModelRow) => words.every((w) => `${r.ref} ${r.label} ${r.best_at} ${r.effort || ""} ${Object.values(r.card?.chips || {}).join(" ")}`
    .toLowerCase().includes(w));
  const out = new Map<string, ModelRow[]>();
  for (const r of rows) if (hit(r)) out.set(r.provider || "other", [...(out.get(r.provider || "other") || []), r]);
  return [...out.entries()];
}

function readFolded(): Record<string, boolean> {
  try {
    const v = JSON.parse(window.localStorage.getItem(FOLD_KEY) || "{}");
    return v && typeof v === "object" ? (v as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function saveFolded(v: Record<string, boolean>): void {
  try {
    window.localStorage.setItem(FOLD_KEY, JSON.stringify(v));
  } catch {
    /* a private window keeps it for this visit only */
  }
}

function Row({ r, on }: { r: ModelRow; on: boolean }) {
  return (
    <label className="su-model" data-on={on || undefined} data-testid="setup-model-row" data-ref={r.ref}>
      <input type="radio" name="setup-model" checked={on} onChange={() => pick("model", r.ref)} data-testid="setup-model-input" data-ref={r.ref} />
      <span className="su-model-ref mono">{r.ref}</span>
      <span className="su-model-label">{r.label !== r.ref ? r.label : ""}</span>
      <span className="su-model-best muted" title="what the best-at cache says it is good at (halo models analyze)">
        {r.best_at}
        {r.effort ? <span className="og-chip mono" data-testid="setup-model-effort" title="what the effort level does on this model">{r.effort}</span> : null}
        <CardChips card={r.card} />
      </span>
      <span className="su-model-num mono muted">{r.price && r.price !== "?" ? r.price : ""}</span>
      <span className="su-model-num mono muted">{r.context && r.context !== "?" ? r.context : ""} <FitMeter fit={r.fit} label={false} /></span>
    </label>
  );
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

function Group({ provider, list, shown, folded, onFold }: { provider: string; list: ModelRow[]; shown: string; folded: boolean; onFold: () => void }) {
  return (
    <section className="su-model-group" data-testid="setup-model-group" data-provider={provider} data-folded={folded || undefined}>
      <button type="button" className="su-group-head mono su-fold" onClick={onFold} aria-expanded={!folded} data-testid="setup-model-fold" data-provider={provider}>
        <Icon name={folded ? "chevron-right" : "chevron-down"} size={12} />
        {provider} <span className="muted">· {list.length}</span>
      </button>
      {!folded && <WindowedRows items={list} render={(r) => <Row key={r.ref} r={r} on={shown === r.ref} />} />}
    </section>
  );
}

export function DefaultModelDetail() {
  const { ready, error } = useLoadState();
  const rows = useSetup((s) => s.data?.models || NONE);
  const shown = useSetup((s) => shownOf(s, "model"));
  const saved = useSetup((s) => s.data?.model || "");
  const [q, setQ] = useState("");
  const [folded, setFolded] = useState<Record<string, boolean>>(readFolded);
  const grouped = useMemo(() => groups(rows, q), [rows, q]);
  if (!ready) return <Waiting error={error} />;
  const known = rows.some((r) => r.ref === saved);
  const matched = grouped.reduce((n, [, l]) => n + l.length, 0);
  const fold = (p: string) => {
    const next = { ...folded, [p]: !folded[p] };
    setFolded(next);
    saveFolded(next);
  };
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
        <>
          <input className="input su-search" type="search" placeholder={`search ${rows.length} models: ref, name, best at`} value={q}
                 onChange={(e) => setQ(e.target.value)} aria-label="Search the models" data-testid="setup-model-search" />
          <div className="su-more muted mono" data-testid="setup-model-count">
            {q ? `${matched} of ${rows.length} models` : `${rows.length} models`}
          </div>
          <div className="su-models" role="radiogroup" aria-label="Default model">
            {grouped.map(([provider, list]) => (
              <Group key={provider} provider={provider} list={list} shown={shown} folded={!q && !!folded[provider]} onFold={() => fold(provider)} />
            ))}
            {grouped.length === 0 && <div className="su-more muted">No model matches {JSON.stringify(q)}.</div>}
          </div>
        </>
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
