// The one plain line per field (3.1.1.0 R3): what each bio field and each
// lineup section and field is for, served by GET /api/field-help from
// halo_harness/field_help.py, the same lines the TUI's read-only bio and
// lineup views show. Loaded once when a form first asks; the bundle carries no
// copy. `useFieldHelp(group, key)` is "" until the lines arrive (or for a
// field that has none).
import { useEffect } from "react";
import { call } from "./api";
import { createStore, useStore } from "./store";

export type HelpGroup = "identity" | "bio" | "lineup_sections" | "lineup_fields" | "assignment";
type Lines = Record<HelpGroup, Record<string, string>>;

const EMPTY: Lines = { identity: {}, bio: {}, lineup_sections: {}, lineup_fields: {}, assignment: {} };
export const fieldHelp = createStore<{ lines: Lines; loaded: boolean }>({ lines: EMPTY, loaded: false });

let loading = false;

export async function loadFieldHelp(): Promise<void> {
  if (loading || fieldHelp.get().loaded) return;
  loading = true;
  try {
    const data = await call<Partial<Lines>>("GET", "field-help");
    fieldHelp.update(() => ({ lines: { ...EMPTY, ...data }, loaded: true }));
  } catch {
    /* an older Studio: the forms show no help lines */
  } finally {
    loading = false;
  }
}

/** The line for `key` in `group` ("bio", "models.preference"); "" when there is none. */
export function useFieldHelp(group: HelpGroup, key: string): string {
  const line = useStore(fieldHelp, (s) => s.lines[group]?.[key] || "");
  useEffect(() => void loadFieldHelp(), []);
  return line;
}

/** Every line of a group (a form with many fields reads them once). */
export function useHelpGroup(group: HelpGroup): Record<string, string> {
  const lines = useStore(fieldHelp, (s) => s.lines[group]);
  useEffect(() => void loadFieldHelp(), []);
  return lines || {};
}
