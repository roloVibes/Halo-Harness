// Agents -> 3 · Map's switcher rows (3.6.0.5 A8, A13, W14): "Auto (the default)" first (no scope words), then his maps
// (and a pack's), then this project's "(this project's)", then the ones that ship with Halo "(ships with Halo)"; each
// keeps the picker's own facts (truthBits.ts pickerSuffix: "· running in {session}", "· new sessions"). "+ New map" is
// MapBar's. Pure: node runs it (tests/test_auto_name_ui.py).
import type { MapRow } from "./mapTypes";
import type { QuietOn } from "./quietOf";
import { pickerSuffix } from "./truthBits";
import { DEFAULT_MAP, isAuto, onMap } from "./truthWords";

export type PickerRow = { value: string; text: string };

export function pickerRows(rows: MapRow[], on: QuietOn[], next: string | null): PickerRow[] {
  const sc = (r: MapRow) => String(r.scope);
  const auto = (r: MapRow) => sc(r) === "starter" && isAuto(r.name, sc(r));
  const row = (r: MapRow, words: string): PickerRow => ({
    value: r.name, text: words + pickerSuffix(on.filter((s) => onMap(s.a, r.name, sc(r))).map((s) => s.title), next === r.name) });
  return [
    ...rows.filter(auto).map((r) => row(r, DEFAULT_MAP)),
    ...rows.filter((r) => sc(r) === "yours" || sc(r) === "pack").map((r) => row(r, r.name)),
    ...rows.filter((r) => sc(r) === "project").map((r) => row(r, `${r.name} (this project's)`)),
    ...rows.filter((r) => sc(r) === "starter" && !auto(r)).map((r) => row(r, `${r.name} (ships with Halo)`)),
  ];
}
