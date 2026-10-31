// "How Halo talks to this model" (3.3.6.0 R4; providers/dialect.py): the dialect record on the card, every field
// editable where it stands, each with its `from` tag (battery, ledger, you, default). An edit is POST
// local/host/<host>/dialect {model, set} (studio/local_card_api.py): marked `user`, it wins over the battery and the
// ledger; "back" puts that field back to what the battery says. The card's next read carries the new record.
import { useState } from "react";
import { api, ApiError } from "../../lib/api";

export type DialectField = { field: string; value: unknown; from: string; title: string; help: string; word: string };
export type DialectView = { fields: DialectField[]; lines: string[] };
type Answer = { view: DialectView; cli: string };

const FROM: Record<string, string> = { battery: "the battery", ledger: "the ledger", user: "you", hub: "the hub", default: "default" };

export function parseRef(ref: string): { model: string; host: string } {
  const r = ref.startsWith("ol:") ? ref.slice(3) : ref;
  const at = r.lastIndexOf("@");
  return at > 0 ? { model: r.slice(0, at), host: r.slice(at + 1) } : { model: r, host: "" };
}

function Control({ f, onSet, busy }: { f: DialectField; onSet: (v: unknown) => void; busy: boolean }) {
  const v = f.value as never;
  const id = `dialect-${f.field}`;
  if (f.field === "instruction_placement" || f.field === "thinking") {
    const opts = f.field === "thinking" ? ["native", "off", "strip"] : ["system", "user-turn"];
    return (
      <select id={id} value={String(v)} disabled={busy} onChange={(e) => onSet(e.target.value)} data-testid="dialect-input" aria-label={f.title}>
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  if (f.field === "strip_fences") {
    return <input id={id} type="checkbox" checked={!!v} disabled={busy} onChange={(e) => onSet(e.target.checked)} data-testid="dialect-input" aria-label={f.title} />;
  }
  if (f.field === "json_repair" || f.field === "loop_guard") {
    const obj = (f.value || {}) as { on?: boolean; attempts?: number; window?: number };
    const key = f.field === "json_repair" ? "attempts" : "window";
    return (
      <span className="dialect-pair">
        <input type="checkbox" checked={!!obj.on} disabled={busy} onChange={(e) => onSet({ ...obj, on: e.target.checked })} aria-label={`${f.title} on`} data-testid="dialect-input" />
        <input className="input mono dialect-num" type="number" min={f.field === "json_repair" ? 0 : 8} max={f.field === "json_repair" ? 3 : 400}
               defaultValue={Number(obj[key] ?? 0)} disabled={busy} aria-label={`${f.title} ${key}`}
               onBlur={(e) => onSet({ ...obj, [key]: parseInt(e.target.value, 10) || 0 })} />
      </span>
    );
  }
  if (f.field === "stop_quirks") {
    return <input id={id} className="input mono" defaultValue={((f.value as string[]) || []).join(", ")} disabled={busy} aria-label={f.title}
                  onBlur={(e) => onSet(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} data-testid="dialect-input" />;
  }
  return (
    <input id={id} className="input mono dialect-num" type="number" min={0} defaultValue={f.value == null ? "" : Number(f.value)} disabled={busy}
           placeholder="the window decides" aria-label={f.title} data-testid="dialect-input"
           onBlur={(e) => onSet(e.target.value === "" ? null : parseInt(e.target.value, 10))} />
  );
}

export function DialectBlock({ view, refName }: { view?: DialectView | null; refName: string }) {
  const [mine, setMine] = useState<DialectView | null>(null);
  const [said, setSaid] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const shown = mine || view;
  if (!shown || !shown.fields?.length) return null;
  const { model, host } = parseRef(refName);
  const send = async (body: Record<string, unknown>) => {
    setBusy(true);
    try {
      const r = await api.post<Answer>(`local/host/${encodeURIComponent(host)}/dialect`, { model, ...body });
      setMine(r.view);
      setSaid({ ok: true, text: r.cli });
    } catch (e) {
      setSaid({ ok: false, text: e instanceof ApiError ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="mprobe-block dialect-block" data-testid="model-card-block" data-block="dialect">
      <span className="rail-label mono">How Halo talks to this model</span>
      <ul className="mprobe-items dialect-fields">
        {shown.fields.map((f) => (
          <li key={f.field} data-testid="dialect-field" data-field={f.field} data-from={f.from} title={f.help}>
            <label className="dialect-name" htmlFor={`dialect-${f.field}`}>{f.title}</label>
            {host ? <Control f={f} busy={busy} onSet={(v) => void send({ set: { [f.field]: v } })} /> : <span className="mono">{f.word}</span>}
            <span className="og-chip mono dialect-from" data-from={f.from}>{FROM[f.from] || f.from}</span>
            {f.from === "user" && host && (
              <button type="button" className="lc-intent" disabled={busy} onClick={() => void send({ reset: f.field })} data-testid="dialect-reset"
                      title="back to what the battery says">back</button>
            )}
          </li>
        ))}
      </ul>
      {said && <div className="mono lc-said" data-ok={said.ok || undefined} data-testid="dialect-said">{said.text}</div>}
    </div>
  );
}
