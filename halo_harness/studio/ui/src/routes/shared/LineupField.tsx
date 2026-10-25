// A LINEUP text field that offers every lineup by name (3.2.2.0 R6): a
// <datalist> fed by `GET lineups`, read when the field first shows and again
// on every `files_changed` frame of kind lineups (lib/filesLive.ts), so a
// lineup a session writes, or `halo teams` removes, is in the list (or gone
// from it) without a reload. Orchestra's goal form uses it.
import { useEffect, useId } from "react";
import { api } from "../../lib/api";
import { onFilesChanged } from "../../lib/filesLive";
import { createStore, useStore } from "../../lib/store";
import { Field } from "../../lib/ui";

const names = createStore<{ list: string[]; started: boolean }>({ list: [], started: false });

async function load(): Promise<void> {
  try {
    const rows = await api.get<{ name: string }[]>("lineups");
    names.update(() => ({ list: Array.isArray(rows) ? rows.map((r) => String(r.name)).filter(Boolean) : [] }));
  } catch {
    /* the field still takes any name */
  }
}

function start(): void {
  if (names.get().started) return;
  names.update(() => ({ started: true }));
  onFilesChanged("lineups", () => void load());
  void load();
}

/** The lineup names (the list a LINEUP field offers), read once and kept current. */
export function useLineupNames(): string[] {
  useEffect(start, []);
  return useStore(names, (s) => s.list);
}

export function LineupField({ label, value, set, example, testid }: { label: string; value: string; set: (v: string) => void; example?: string; testid?: string }) {
  const list = useLineupNames();
  const dl = useId();
  return (
    <Field label={label}>
      {(id) => (
        <>
          <input id={id} className="input mono" value={value} placeholder={example} list={dl} onChange={(e) => set(e.target.value)} data-testid={testid} />
          <datalist id={dl} data-testid={testid ? `${testid}-names` : undefined}>
            {list.map((n) => <option key={n} value={n} />)}
          </datalist>
        </>
      )}
    </Field>
  );
}
