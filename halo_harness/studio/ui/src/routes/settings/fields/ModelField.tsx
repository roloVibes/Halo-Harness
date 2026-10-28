// A model row's control (3.3.5.0 R0 (f)): the text field, and under it the
// catalog's every model (GET models, the Roles picker's rows) behind "pick
// from the list": a search box, a count line and the full list (drawn a
// window at a time past 200 rows, lib/ui/WindowedRows); a click saves that ref.
import { useEffect, useMemo, useState } from "react";
import { api } from "../../../lib/api";
import { WindowedRows } from "../../../lib/ui";
import { TextField } from "./Text";

type Row = { ref: string; provider?: string; context?: string; effort_word?: string };

export function ModelField({ id, value, fallback, label, disabled, onSave }: {
  id?: string;
  value: unknown;
  fallback: unknown;
  label: string;
  disabled?: boolean;
  onSave: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    if (!open || rows !== null) {
      return;
    }
    api.get<Row[]>("models").then((r) => setRows(Array.isArray(r) ? r : []), (e) => {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    });
  }, [open, rows]);
  const hit = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean);
    return (rows || []).filter((r) => words.every((w) => `${r.ref} ${r.provider || ""} ${r.effort_word || ""}`.toLowerCase().includes(w)));
  }, [rows, q]);
  return (
    <div className="st-model" data-testid="settings-model">
      <TextField id={id} value={value} fallback={fallback} label={label} disabled={disabled} onSave={onSave} />
      <button type="button" className="st-model-open muted" onClick={() => setOpen(!open)} aria-expanded={open} data-testid="settings-model-open">
        {open ? "hide the list" : "pick from the list"}
      </button>
      {open && (
        <div className="st-model-list" data-testid="settings-model-list">
          {rows === null ? <span className="muted mono">reading the catalog...</span> : (
            <>
              <input className="st-input mono" type="search" placeholder={`search ${rows.length} models`} value={q}
                     onChange={(e) => setQ(e.target.value)} aria-label="Search the models" />
              <span className="muted mono" data-testid="settings-model-count">{q ? `${hit.length} of ${rows.length} models` : `${rows.length} models`}</span>
              {error && <span className="muted">{error}</span>}
              <div className="st-model-rows">
                <WindowedRows items={hit} render={(r) => (
                  <button key={r.ref} type="button" className="st-model-row mono" disabled={disabled} data-testid="settings-model-row" data-ref={r.ref}
                          aria-pressed={String(value || "") === r.ref} onClick={() => onSave(r.ref)}>
                    <span>{r.ref}</span>
                    <span className="muted">{[r.context && r.context !== "?" ? r.context : "", r.effort_word || ""].filter(Boolean).join(" · ")}</span>
                  </button>
                )} />
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
