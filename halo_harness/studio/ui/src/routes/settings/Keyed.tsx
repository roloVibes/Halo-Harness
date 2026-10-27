// A keyed row's control (3.3.3.0 R2): a key with a placeholder segment
// (connectors.<slug>.enabled, providers.<name>.enabled, ollama.hosts[].ssh ...)
// describes one field of many entries. The entries the saved config holds (and
// the ones the catalog knows, such as every provider) are a small table, the
// field's own control on each with its own Reset; under it, behind a
// disclosure, the whole section as JSON (adding an entry is writing it there).
import { Button } from "../../lib/ui";
import { Control } from "./Control";
import { JsonEditor } from "./fields/JsonEditor";
import { resetValue, setValue, useSettings, type Row, type Value } from "./store";

function placeholder(key: string): string {
  const m = /<([^>]+)>|\[\]/.exec(key);
  return m ? m[1] || "name" : "entry";
}

export function Keyed({ row, v, problems }: { row: Row; v: Value | undefined; problems?: string[] }) {
  const busy = useSettings((s) => s.busy);
  const entries = v?.entries || [];
  const kind = row.leaf_kind || "string";
  return (
    <div className="st-keyed-box">
      {entries.length > 0 ? (
        <table className="st-keyed" data-testid="settings-keyed">
          <thead>
            <tr>
              <th className="mono">{placeholder(row.key)}</th>
              <th className="mono">{row.leaf || "value"}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.key} data-testid="settings-entry" data-key={e.key} data-set={e.set}>
                <td className="mono st-entry-name">{e.name}</td>
                <td>
                  <Control kind={kind} rowKey={row.key} keyName={e.key} label={`${row.title}: ${e.name}`} value={e.value} fallback={row.default}
                           choices={row.choices} isSet={e.set} secret={row.secret} busy={busy === e.key} />
                </td>
                <td>
                  <Button size="sm" variant="ghost" disabled={!e.set || busy === e.key} onClick={() => void resetValue(e.key, row.key)}
                          data-testid="settings-entry-reset" title={`remove ${e.key} from config.json`}>
                    Reset
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="st-none muted" data-testid="settings-keyed-none">
          No {placeholder(row.key)} is saved yet: add one in {row.section} as JSON.
        </p>
      )}
      <details className="st-section" data-testid="settings-section">
        <summary className="mono">Edit {row.section} as JSON</summary>
        <JsonEditor value={v?.section} label={`${row.section} as JSON`} problems={problems} testid="settings-section-json"
                    disabled={busy === row.section} onSave={(t) => void setValue(row.section || row.key, t, row.key)} />
      </details>
    </div>
  );
}
