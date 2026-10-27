// The Settings section's store (3.3.3.0 R2): `GET settings/catalog` read once
// (the rows and the groups of halo_harness/settings_catalog.py), `GET
// settings/values` read once and again whenever config.json moves on disk
// (`files_changed`: a `halo config set` in a terminal, another Studio, Setup),
// and each row's last answer: the "saved · takes effect now" flash, or the
// problems the server said. A change posts through `act` (Setup's shape,
// routes/setup/store.ts) and the answer carries the row's fresh value.
import { api, ApiError } from "../../lib/api";
import { onFilesChanged } from "../../lib/filesLive";
import { createStore, setSectionStatus, toast, useStore } from "../../lib/store";

export type Kind = "bool" | "enum" | "int" | "float" | "string" | "list" | "mapping" | "model" | "path" | "keyed";
export type Effect = "now" | "next session" | "next launch";
export type Row = {
  key: string;
  group: string;
  title: string;
  kind: Kind;
  default: unknown;
  choices: string[];
  help: string;
  effect: Effect;
  effect_words: string;
  secret: boolean;
  page: string;
  /** keyed rows: the control of one entry, the section the entries live in, the field of each, a list section. */
  leaf_kind?: Kind;
  section?: string;
  leaf?: string;
  listy?: boolean;
  entry_names?: string[];
};
export type Group = { id: string; title: string; count: number };
export type Entry = { name: string; key: string; value: unknown; set: boolean };
export type Value = { value: unknown; set: boolean; default: unknown; masked: boolean; cli: string; entries?: Entry[]; section?: unknown };
export type Answer = { ok: boolean; lines: string[]; at: number };

export type SettingsState = {
  rows: Row[];
  groups: Group[];
  values: Record<string, Value>;
  loaded: boolean;
  error: string;
  busy: string;
  last: Record<string, Answer | undefined>;
};

export const settings = createStore<SettingsState>({ rows: [], groups: [], values: {}, loaded: false, error: "", busy: "", last: {} });

export function useSettings<S>(select: (s: SettingsState) => S): S {
  return useStore(settings, select);
}

/** The row of `key` (a keyed row by its placeholder key). */
export function rowOf(key: string): Row | undefined {
  return settings.get().rows.find((r) => r.key === key);
}

function showStatus(): void {
  const s = settings.get();
  const n = Object.values(s.values).filter((v) => v.set).length;
  setSectionStatus("settings", `${n} of ${s.rows.length} keys set · ~/.halo/config.json`);
}

let catalogLoading: Promise<void> | null = null;

/** The catalog, read once (the section, the palette's "Settings: <title>" entries). */
export function loadCatalog(): Promise<void> {
  if (settings.get().rows.length) return Promise.resolve();
  if (!catalogLoading)
    catalogLoading = (async () => {
      try {
        const c = await api.get<{ rows: Row[]; groups: Group[] }>("settings/catalog");
        settings.update(() => ({ rows: c.rows, groups: c.groups }));
      } catch (e) {
        settings.update(() => ({ error: e instanceof Error ? e.message : String(e) }));
        catalogLoading = null;
      }
    })();
  return catalogLoading;
}

let loading: Promise<void> | null = null;
let again = false;

/** Read the values; one asked for while a read is under way runs once more after it. */
export async function loadValues(): Promise<void> {
  if (loading) {
    again = true;
    return loading;
  }
  loading = (async () => {
    try {
      const v = await api.get<{ values: Record<string, Value> }>("settings/values");
      settings.update(() => ({ values: v.values, loaded: true, error: "" }));
      showStatus();
    } catch (e) {
      settings.update(() => ({ loaded: true, error: e instanceof Error ? e.message : String(e) }));
    } finally {
      loading = null;
      if (again) {
        again = false;
        void loadValues();
      }
    }
  })();
  return loading;
}

let started = false;

/** Start once (the section's view or a door): the catalog, the values and the files watcher. */
export function startSettings(): void {
  if (started) return;
  started = true;
  onFilesChanged(["config"], () => void loadValues());
  void loadCatalog();
  void loadValues();
}

type SetAnswer = { key: string; row: string; line: string; effect_words: string; entry: Value };

/** POST one change (settings/set or settings/unset); the answer is the row's fresh value and its flash line. */
export async function act(path: "settings/set" | "settings/unset", body: { key: string; value?: unknown }, row: string): Promise<boolean> {
  settings.update(() => ({ busy: body.key }));
  try {
    const r = await api.post<SetAnswer>(path, body);
    const at = Date.now();
    settings.update((s) => ({
      values: { ...s.values, [r.row || row]: r.entry },
      last: { ...s.last, [row]: { ok: true, lines: [r.line], at } },
    }));
    showStatus();
    void loadValues(); // a keyed entry or a section moves the other rows that read it too
    window.setTimeout(() => settings.update((s) => (s.last[row]?.at === at ? { last: { ...s.last, [row]: undefined } } : {})), 8000);
    return true;
  } catch (e) {
    const lines = e instanceof ApiError && e.problems.length ? e.problems : [e instanceof Error ? e.message : String(e)];
    settings.update((s) => ({ last: { ...s.last, [row]: { ok: false, lines, at: Date.now() } } }));
    toast(lines[0], "error", 6000);
    return false;
  } finally {
    settings.update(() => ({ busy: "" }));
  }
}

/** Save `value` to `key` (a row's key, a keyed row's entry key, or its section); `row` is the row it shows under. */
export function setValue(key: string, value: unknown, row = key): Promise<boolean> {
  return act("settings/set", { key, value }, row);
}

/** Reset to default: the key leaves config.json. */
export function resetValue(key: string, row = key): Promise<boolean> {
  return act("settings/unset", { key }, row);
}
