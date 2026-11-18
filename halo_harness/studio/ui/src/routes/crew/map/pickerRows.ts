// Agents -> 3 · Map's switcher rows (3.6.0.5 A8, A13, W14): "Auto (the default)" first (no scope words), then his maps
// (and a pack's), then this project's "(this project's)", then the ones that ship with Halo "(ships with Halo)"; each
// keeps the picker's own facts (truthBits.ts pickerSuffix: "· running in {session}", "· new sessions"). "+ New map" is
// MapBar's. A5: his own old file named auto or starter is a row of its own among his, "{name} · your copy from before",
// opened and copied by its scope (value `{scope}:{name}`). Pure: node runs it (tests/test_auto_name_ui.py); mapStore.ts
// and oldCopy.ts re-export mapUrl, pickerValue and copyName.
import type { MapRow } from "./mapTypes";
import type { QuietOn } from "./quietOf";
import { pickerSuffix } from "./truthBits";
import { DEFAULT_MAP, isAuto, isOldDefault, onMap } from "./truthWords";

export type PickerRow = { value: string; text: string };

/** A5: the words of his own old file (the picker row, the Map's bar, Setup's row). */
export const oldWords = (name: string): string => `${name} · your copy from before`;

/** The switcher's value of a map: `{scope}:{name}` when it is opened by its scope (his old file), else the name. */
export const pickerValue = (name: string, scope = ""): string => (scope ? `${scope}:${name}` : name);

/** The address of a map's detail: GET crew/map/<name>, with `?scope=` when it is opened by its scope. */
export const mapUrl = (name: string, scope = ""): string => `crew/map/${name}${scope ? `?scope=${scope}` : ""}`;

/** The copy of his old file: "my-map", else the first free "my-map-{k}" from k = 2. */
export function copyName(names: string[]): string {
  if (!names.includes("my-map")) return "my-map";
  for (let k = 2; ; k++) if (!names.includes(`my-map-${k}`)) return `my-map-${k}`;
}

/** What the bar's uses slot draws (A5, A11, moved.md Q3): "old" his old file (its words and Copy, no switch); on Auto
 *  "default" (none set, roles on: the sentence), "none" (new sessions get no map: NEXT_NONE alone), "" (a map of his
 *  is set: nothing); every other map "switch". */
export function usesSlot(name: string, scope: string, next: string | null, nextNone: boolean): "old" | "default" | "none" | "switch" | "" {
  if (isOldDefault(name, scope)) return "old";
  if (isAuto(name, scope)) return nextNone ? "none" : !next ? "default" : "";
  return "switch";
}

export function pickerRows(rows: MapRow[], on: QuietOn[], next: string | null): PickerRow[] {
  const sc = (r: MapRow) => String(r.scope);
  const auto = (r: MapRow) => sc(r) === "starter" && isAuto(r.name, sc(r));
  const old = (r: MapRow) => isOldDefault(r.name, sc(r));
  const row = (r: MapRow, words: string): PickerRow => ({
    value: r.name, text: words + pickerSuffix(on.filter((s) => onMap(s.a, r.name, sc(r))).map((s) => s.title), next === r.name) });
  return [
    ...rows.filter(auto).map((r) => row(r, DEFAULT_MAP)),
    // his maps (and a pack's) in store order; his old file among them, no suffix: no session runs it, it is never next
    ...rows.filter((r) => sc(r) === "yours" || sc(r) === "pack" || old(r))
      .map((r) => (old(r) ? { value: pickerValue(r.name, sc(r)), text: oldWords(r.name) } : row(r, r.name))),
    ...rows.filter((r) => sc(r) === "project" && !old(r)).map((r) => row(r, `${r.name} (this project's)`)),
    ...rows.filter((r) => sc(r) === "starter" && !auto(r)).map((r) => row(r, `${r.name} (ships with Halo)`)),
  ];
}
