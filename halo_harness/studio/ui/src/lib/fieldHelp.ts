// The one plain line per field (3.1.1.0 R3): what each bio field and each
// lineup section and field is for, served by GET /api/field-help from
// halo_harness/field_help.py, the same lines the TUI's read-only bio and
// lineup views show. Loaded once when a form first asks; the bundle carries no
// copy. `useFieldHelp(group, key)` is "" until the lines arrive (or for a
// field that has none).
import { useEffect } from "react";
import { call } from "./api";
import { createStore, useStore } from "./store";

/** 3.1.4.0 R4: `model_select` holds the lines of the one model control (routes/shared/ModelSelect.tsx); 3.3.16.0 R1b:
 *  `lineup_defaults` what Halo does when a lineup leaves a section out (the inspector's "not set = Halo does ..."). */
export type HelpGroup = "identity" | "bio" | "lineup_sections" | "lineup_fields" | "assignment" | "model_select" | "lineup_defaults";
type Lines = Record<HelpGroup, Record<string, string>>;

const EMPTY: Lines = { identity: {}, bio: {}, lineup_sections: {}, lineup_fields: {}, assignment: {}, model_select: {}, lineup_defaults: {} };
// `asked`: the answer landed or failed (3.6.0.0 R5c: a form whose help lines push its controls down waits for it)
export const fieldHelp = createStore<{ lines: Lines; loaded: boolean; asked: boolean }>({ lines: EMPTY, loaded: false, asked: false });

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
    fieldHelp.update(() => ({ asked: true }));
  }
}

/** 3.6.0.0 R5c: the help lines have landed (or cannot): a form that shows them under its fields is drawn whole after
 *  this, so a line landing never moves a control a person is about to click (the goal form's Review the plan first
 *  moved 41 px down). */
export function useHelpAsked(): boolean {
  const asked = useStore(fieldHelp, (s) => s.asked);
  useEffect(() => void loadFieldHelp(), []);
  return asked;
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
