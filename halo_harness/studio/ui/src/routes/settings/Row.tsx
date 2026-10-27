// One Settings row (3.3.3.0 R2): the title and the key, the help line, the
// control (its kind's field; a keyed row's table of entries), the "default"
// marker while the key is unset, the value it falls back to, Reset to
// default, and the exact `halo config set ...` line in mono as its footer. A
// change saves at once and the row says "saved · takes effect now" (or in the
// next session, or on the next launch) for a few seconds; a refusal's problem
// lines show under the control. A secret row never shows its value.
import { useId } from "react";
import { Button } from "../../lib/ui";
import { Control, usesJson } from "./Control";
import { Keyed } from "./Keyed";
import { usePages } from "./pages";
import { resetValue, useSettings, type Row } from "./store";

function word(v: unknown): string {
  if (v === null || v === undefined) return "unset";
  return typeof v === "string" ? v : JSON.stringify(v);
}

export function SettingRow({ row }: { row: Row }) {
  const id = useId();
  const v = useSettings((s) => s.values[row.key]);
  const last = useSettings((s) => s.last[row.key]);
  const busy = useSettings((s) => s.busy === row.key);
  const lit = usePages((s) => s.lit === row.key);
  const isSet = !!v?.set;
  const problems = last && !last.ok ? last.lines : undefined;
  const json = row.kind !== "keyed" && usesJson(row.kind, row.key, v?.value, row.default);
  return (
    <article className="st-row" data-testid="settings-row" data-key={row.key} data-kind={row.kind} data-set={isSet} data-lit={lit || undefined}
             aria-label={row.title}>
      <header className="st-row-head">
        <label className="st-row-title" htmlFor={id}>
          {row.title}
        </label>
        <code className="st-row-key mono">{row.key}</code>
        {!isSet && (
          <span className="st-default mono" data-testid="settings-default" title="not in config.json: Halo uses the default">
            default
          </span>
        )}
        {v?.masked && (
          <span className="st-masked mono" data-testid="settings-masked">
            set, hidden
          </span>
        )}
      </header>
      <p className="st-row-help">{row.help}</p>
      <div className="st-row-control">
        {row.kind === "keyed" ? (
          <Keyed row={row} v={v} problems={problems} />
        ) : (
          <>
            <Control id={id} kind={row.kind} rowKey={row.key} keyName={row.key} label={row.title} value={v?.value} fallback={row.default}
                     choices={row.choices} isSet={isSet} secret={row.secret} busy={busy} problems={problems} />
            <Button size="sm" variant="ghost" disabled={!isSet || busy} onClick={() => void resetValue(row.key)} data-testid="settings-reset"
                    title="remove the key from config.json: Halo uses the default again">
              Reset to default
            </Button>
          </>
        )}
      </div>
      <div className="st-row-meta mono">
        <span className="muted">default {row.secret ? "unset" : word(row.default)}</span>
        <span className="muted">· {row.effect_words}</span>
        {last?.ok && (
          <span className="st-saved" data-testid="settings-saved" role="status">
            saved · {row.effect_words}
          </span>
        )}
      </div>
      {problems && !json && (
        <ul className="st-problems" data-testid="settings-problems" role="alert">
          {problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}
      <footer className="st-row-cli mono" data-testid="settings-cli" title="the same change from a terminal">
        {v?.cli || `halo config set ${row.key} <value>`}
      </footer>
    </article>
  );
}
