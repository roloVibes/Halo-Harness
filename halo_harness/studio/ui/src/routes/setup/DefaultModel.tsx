// setup-model (3.3.0.0 R1): the default model -- the Models panel's rows for
// the providers set up here (studio/model.py model_rows: the catalog, the
// best-at line), grouped by provider, a search box over ref, name and best
// at, the saved one checked; Save writes `model` in ~/.halo/config.json, the
// model a new session starts on (`halo --model` and /model still pick
// another for one run). 3.3.0.0 R3: the rows are the cached catalog (reading
// this page probes no host); a configured Ollama host nothing has read yet
// says "not read yet: Refresh", and Refresh reads every provider's list
// (POST models/refresh, the Models panel's Refresh), then the page again.
import { useMemo, useState } from "react";
import { api } from "../../lib/api";
import { toast } from "../../lib/store";
import { Button, Empty } from "../../lib/ui";
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { loadSetup, NONE, pick, shownOf, useSetup, type ModelRow } from "./store";

const LIMIT = 60; // rows drawn per provider until the search narrows them

function groups(rows: ModelRow[], q: string): [string, ModelRow[]][] {
  const words = q.toLowerCase().split(/\s+/).filter(Boolean);
  const hit = (r: ModelRow) => words.every((w) => `${r.ref} ${r.label} ${r.best_at}`.toLowerCase().includes(w));
  const out = new Map<string, ModelRow[]>();
  for (const r of rows) if (hit(r)) out.set(r.provider || "other", [...(out.get(r.provider || "other") || []), r]);
  return [...out.entries()];
}

function Row({ r, on }: { r: ModelRow; on: boolean }) {
  return (
    <label className="su-model" data-on={on || undefined} data-testid="setup-model-row" data-ref={r.ref}>
      <input type="radio" name="setup-model" checked={on} onChange={() => pick("model", r.ref)} data-testid="setup-model-input" data-ref={r.ref} />
      <span className="su-model-ref mono">{r.ref}</span>
      <span className="su-model-label">{r.label !== r.ref ? r.label : ""}</span>
      <span className="su-model-best muted" title="what the best-at cache says it is good at (halo models analyze)">{r.best_at}</span>
      <span className="su-model-num mono muted">{r.price && r.price !== "?" ? r.price : ""}</span>
      <span className="su-model-num mono muted">{r.context && r.context !== "?" ? r.context : ""}</span>
    </label>
  );
}

function Refresh() {
  const notes = useSetup((s) => s.data?.model_notes || NONE);
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      const r = await api.post<{ rows?: number }>("models/refresh", {});
      toast(`the catalog read again: ${r.rows ?? 0} models`, "done", 4000);
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error", 6000);
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
    </div>
  );
}

export function DefaultModelDetail() {
  const { ready, error } = useLoadState();
  const rows = useSetup((s) => s.data?.models || NONE);
  const shown = useSetup((s) => shownOf(s, "model"));
  const saved = useSetup((s) => s.data?.model || "");
  const [q, setQ] = useState("");
  const grouped = useMemo(() => groups(rows, q), [rows, q]);
  if (!ready) return <Waiting error={error} />;
  const known = rows.some((r) => r.ref === saved);
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
          <div className="su-models" role="radiogroup" aria-label="Default model">
            {grouped.map(([provider, list]) => (
              <section key={provider} className="su-model-group" data-testid="setup-model-group" data-provider={provider}>
                <div className="su-group-head mono">
                  {provider} <span className="muted">· {list.length}</span>
                </div>
                {list.slice(0, q ? list.length : LIMIT).map((r) => (
                  <Row key={r.ref} r={r} on={shown === r.ref} />
                ))}
                {!q && list.length > LIMIT && <div className="su-more muted">{list.length - LIMIT} more: search to narrow the list</div>}
              </section>
            ))}
            {grouped.length === 0 && <div className="su-more muted">No model matches {JSON.stringify(q)}.</div>}
          </div>
        </>
      )}
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
