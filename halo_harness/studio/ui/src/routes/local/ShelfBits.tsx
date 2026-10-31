// Local -> Models' shelf (3.3.6.0 R4; models_library/shelf.py, studio/local_shelf_api.py): the row's hint ("not used
// in 30 days, 17 GB"), the Retire card a row's actions menu opens (the uses card first, a why, Retire: the existing
// delete with a shelf line so a re-pull is one click) and the folded Shelf block at the bottom of the page (the
// retired models, each with Re-pull: the existing pull job; a fitted twin shows its recipe instead).
import { useEffect, useState } from "react";
import { Button } from "../../lib/ui";
import { api, ApiError } from "../../lib/api";
import { line, retireModel, useCtl } from "./ctl";
import { loadModels, useLocal } from "./store";
import type { ModelEntry, ShelfRow } from "./types";

export function ShelfHint({ m }: { m: ModelEntry }) {
  const h = m.shelf?.hint;
  if (!h) return null;
  return (
    <span className="og-chip mono lc-shelf-hint" data-testid="local-model-shelf-hint"
          title="its last answered call in the traffic ledger and its size on disk: Retire (the ... menu) frees the disk and keeps a note">
      {h}
    </span>
  );
}

export function RetireCard({ host, m }: { host: string; m: ModelEntry }) {
  const u = useCtl((c) => c.uses);
  const busy = useCtl((c) => c.busy);
  const said = useCtl((c) => c.said);
  const [why, setWhy] = useState(m.shelf?.hint || "");
  if (!u) return <p className="mono muted">reading what uses it…</p>;
  const force = u.any;
  const cli = `halo models retire ${m.model} --host ${host}` + (force ? " --force" : "");
  return (
    <div className="lc-act-body" data-testid="local-retire" data-any={u.any || undefined}>
      <p className="lc-why">Retire deletes it from {host} (the delete's own path) and leaves a note on the shelf: Re-pull brings it back.</p>
      <p className="lc-why" data-testid="local-retire-uses">{u.line}</p>
      <input className="input mono" value={why} onChange={(e) => setWhy(e.target.value)} placeholder="why (kept with the note)"
             aria-label="why it is retired" data-testid="local-retire-why" />
      {!said?.ok && (
        <Button size="sm" variant="primary" disabled={busy || u.live > 0} onClick={() => void retireModel(host, m.model, why, force)}
                data-testid="local-retire-go" title={u.live > 0 ? "a live session is on it" : cli}>
          {force ? "Retire anyway" : "Retire"}
        </Button>
      )}
      <code className="mono lc-cli-line" data-testid="local-act-cli" title="the same from a terminal">{cli}</code>
    </div>
  );
}

export function ShelfBlock({ host }: { host?: string }) {
  const [rows, setRows] = useState<ShelfRow[] | null>(null);
  const [said, setSaid] = useState<{ ok: boolean; text: string } | null>(null);
  const models = useLocal((s) => s.models); // a Retire or a pull reads the models again: the shelf follows
  const read = async () => {
    try {
      const r = await api.get<{ shelf: ShelfRow[] }>("local/shelf", host ? { host } : undefined);
      setRows(r.shelf);
    } catch {
      setRows([]);
    }
  };
  useEffect(() => {
    void read();
  }, [host, models]);
  const repull = async (r: ShelfRow) => {
    try {
      await api.post("local/shelf/repull", { host: r.host, model: r.model });
      setSaid({ ok: true, text: `pulling ${r.model} onto ${r.host} (the Jobs list shows it)` });
      void read();
      void loadModels();
    } catch (e) {
      setSaid({ ok: false, text: e instanceof ApiError ? e.message : String(e) });
    }
  };
  return (
    <details className="lc-block lc-shelf" data-testid="local-shelf">
      <summary className="rail-label mono">SHELF · {rows ? rows.length : "…"} RETIRED</summary>
      {rows && !rows.length && <p className="muted">Nothing retired. A model's ... menu has Retire: it frees the disk and keeps a note here.</p>}
      <ul className="lc-model-list">
        {(rows || []).map((r) => (
          <li key={`${r.host}|${r.model}`} className="lc-shelf-row mono" data-testid="local-shelf-row" data-model={r.model} data-host={r.host}>
            <b>{r.model}</b> <span className="muted">from {r.host} · {String(r.retired_at).slice(0, 10)} · {r.why}</span>
            <span className="spacer" />
            {r.repull.startsWith("ollama pull ") ? (
              <Button size="sm" onClick={() => void repull(r)} data-testid="local-shelf-repull" title={line("pull", r.host, r.model)}>Re-pull</Button>
            ) : (
              <code className="lc-cli-line" title="a fitted twin: re-make it">{r.repull}</code>
            )}
          </li>
        ))}
      </ul>
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="local-shelf-said">{said.text}</div>}
    </details>
  );
}
