// One generic field per kind (3.3.3.0 R2): bool a switch, enum a select, int
// and float a number field, string / model / path a text field, list one item
// per line, mapping the JSON editor. A list of entries that are mappings
// (ollama.hosts, the Hugging Face endpoints and servers, or any list that
// holds a mapping now) is edited as JSON too. Every control saves `key`
// through the store and shows under row `row`.
import { JsonEditor } from "./fields/JsonEditor";
import { ListEditor } from "./fields/ListEditor";
import { NumberField } from "./fields/Number";
import { Select } from "./fields/Select";
import { TextField } from "./fields/Text";
import { Toggle } from "./fields/Toggle";
import { setValue, type Kind } from "./store";

const ENTRY_LISTS = new Set(["ollama.hosts", "huggingface.endpoints", "huggingface.local_servers"]);

function holdsMapping(v: unknown): boolean {
  return Array.isArray(v) && v.some((x) => x !== null && typeof x === "object");
}

/** Is this control the JSON editor (its problems show under it, not under the row). */
export function usesJson(kind: Kind, keyName: string, value: unknown, fallback: unknown): boolean {
  return kind === "mapping" || (kind === "list" && (ENTRY_LISTS.has(keyName) || holdsMapping(value) || holdsMapping(fallback)));
}

export function Control({ id, kind, rowKey, keyName, label, value, fallback, choices, isSet, secret, busy, problems }: {
  id?: string;
  kind: Kind;
  rowKey: string;
  keyName: string;
  label: string;
  value: unknown;
  fallback: unknown;
  choices: string[];
  isSet: boolean;
  secret?: boolean;
  busy?: boolean;
  problems?: string[];
}) {
  const save = (v: unknown) => void setValue(keyName, v, rowKey);
  const shown = isSet ? value : null;
  switch (kind) {
    case "bool":
      return <Toggle id={id} value={isSet ? value : fallback} label={label} disabled={busy} onSave={save} />;
    case "enum":
      return <Select id={id} value={shown} choices={choices} fallback={fallback} label={label} disabled={busy} onSave={save} />;
    case "int":
    case "float":
      return <NumberField id={id} value={shown} fallback={fallback} float={kind === "float"} label={label} disabled={busy} onSave={save} />;
    case "list":
      if (usesJson(kind, keyName, value, fallback))
        return <JsonEditor id={id} value={shown} label={label} problems={problems} disabled={busy} onSave={save} />;
      return <ListEditor id={id} value={shown} fallback={fallback} label={label} disabled={busy} onSave={save} />;
    case "mapping":
      return <JsonEditor id={id} value={shown} label={label} problems={problems} disabled={busy} onSave={save} />;
    default:
      return <TextField id={id} value={shown} fallback={fallback} secret={secret} isSet={isSet} label={label} disabled={busy} onSave={save} />;
  }
}
