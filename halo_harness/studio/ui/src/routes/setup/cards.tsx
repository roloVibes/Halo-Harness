// The Providers and Local models blocks' shared parts (3.3.0.0 R2): `send`
// posts one card's form (a provider's Save & test, an Ollama host, a Hugging
// Face entry, a model folder, the runtime) and the answer is the fresh state,
// so every card and the status strip redraw from it; each card keeps the
// lines its last post answered (what was written and what the test found, or
// the problems). A key typed into a form is posted once and the form forgets
// it; the state that comes back carries only "set", where from and ****1234.
import { useState } from "react";
import { api, ApiError } from "../../lib/api";
import { createStore, toast, useStore } from "../../lib/store";
import { Button } from "../../lib/ui";
import { setup, showStatus, type Answer, type SetupData } from "./store";

type Cards = { busy: string; last: Record<string, Answer> };
export const cards = createStore<Cards>({ busy: "", last: {} });

export function useCards<S>(select: (s: Cards) => S): S {
  return useStore(cards, select);
}

/** POST one card's form; true when it saved. */
export async function send(card: string, path: string, body: Record<string, unknown>): Promise<boolean> {
  cards.update(() => ({ busy: card }));
  try {
    const r = await api.post<SetupData & { lines?: string[] }>(path, body);
    const { lines, ...data } = r;
    setup.update(() => ({ data: data as SetupData }));
    showStatus(data as SetupData);
    cards.update((s) => ({ last: { ...s.last, [card]: { ok: true, lines: lines || [] } } }));
    toast(lines?.[0] || "Saved", "done", 4000);
    return true;
  } catch (e) {
    const lines = e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)];
    cards.update((s) => ({ last: { ...s.last, [card]: { ok: false, lines } } }));
    toast(lines[0], "error", 6000);
    return false;
  } finally {
    cards.update(() => ({ busy: "" }));
  }
}

/** The lines a card's last post answered, under the card. */
export function CardLines({ card }: { card: string }) {
  const last = useCards((s) => s.last[card]);
  if (!last || !last.lines.length) return null;
  return (
    <pre className="su-lines mono" data-ok={last.ok || undefined} data-testid="setup-card-lines" data-card={card}>
      {last.lines.join("\n")}
    </pre>
  );
}

export type Input = { id: string; label: string; secret?: boolean; placeholder?: string };

/** A row of inputs and its button. A secret is a password field, never prefilled; every field empties after a save. */
export function MiniForm({ card, inputs, button, title, onSave, allowBlank = false }: {
  card: string;
  inputs: Input[];
  button: string;
  title?: string;
  onSave: (values: Record<string, string>) => Promise<boolean>;
  allowBlank?: boolean;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const busy = useCards((s) => s.busy);
  const typed = Object.values(values).some((v) => v.trim());
  const go = async () => {
    if (await onSave(values)) setValues({});
  };
  return (
    <form className="su-form" data-testid="setup-form" data-card={card} onSubmit={(e) => { e.preventDefault(); if (!busy && (typed || allowBlank)) void go(); }}>
      {inputs.map((f) => (
        <label key={f.id} className="su-input">
          <span className="su-input-label mono">{f.label}</span>
          <input className="input" type={f.secret ? "password" : "text"} autoComplete={f.secret ? "new-password" : "off"} spellCheck={false}
                 placeholder={f.placeholder ?? (f.secret ? "paste a key" : "")} value={values[f.id] || ""}
                 onChange={(e) => setValues((v) => ({ ...v, [f.id]: e.target.value }))} data-testid="setup-input" data-card={card} data-field={f.id} />
        </label>
      ))}
      <Button type="submit" variant="primary" size="sm" disabled={!!busy || (!typed && !allowBlank)} title={title} data-testid="setup-card-save" data-card={card}>
        {busy === card ? "Saving..." : button}
      </Button>
    </form>
  );
}

/** A small table: the head, then one row per entry with its remove button; column `wrap` (the URL or the path) wraps. */
export function Table({ card, head, rows, onRemove, wrap = 1 }: {
  card: string;
  head: string[];
  rows: { key: string; cells: string[] }[];
  onRemove: (key: string) => void;
  wrap?: number;
}) {
  const busy = useCards((s) => s.busy);
  if (!rows.length) return null;
  return (
    <table className="su-table" data-testid="setup-table" data-card={card}>
      <thead>
        <tr>
          {head.map((h) => (
            <th key={h} className="mono">{h}</th>
          ))}
          <th />
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.key} data-testid="setup-row" data-card={card} data-key={r.key}>
            {r.cells.map((c, i) => (
              <td key={i} className={(i ? "mono muted" : "mono") + (i === wrap ? " su-wrap" : "")}>{c}</td>
            ))}
            <td className="su-table-act">
              <Button variant="ghost" size="sm" disabled={!!busy} onClick={() => onRemove(r.key)} data-testid="setup-remove" data-card={card} data-key={r.key}>
                Remove
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
