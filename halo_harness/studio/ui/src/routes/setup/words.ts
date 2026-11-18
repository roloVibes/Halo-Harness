// Setup's strip and glance words (3.6.0.5 A8, W14; the decisions' theme should). pages.ts re-exports them. Pure: node
// runs it (tests/test_auto_name_ui.py).
import type { SetupData } from "./store";
import { DEFAULT_MAP, isAuto } from "../crew/map/truthWords";

/** The map new sessions run on, as a person reads it: "Auto (the default)" for the default, else the map's name. */
export function mapWord(d: Pick<SetupData, "team">): string {
  return isAuto(d.team.active) ? DEFAULT_MAP : d.team.active;
}

/** The theme as a person reads it: the setting whose id is `auto` follows the system; unset, the default's name. */
export function themeWord(d: Pick<SetupData, "theme" | "theme_default">): string {
  return d.theme === "auto" ? "Follow the system" : d.theme || `${d.theme_default} (default)`;
}
