// `studio.hover_cards` (Settings -> Studio; on by default): "on" draws the hover cards and takes the plain `title`
// tooltips off the boxes that have one, "off" is the page as it was before them (the titles back, no card), "wait" while
// the values are still being read (no card yet, no title either: never two tooltips at once). The value is the Settings
// store's (GET settings/values, read again when config.json moves), so a change in Settings or `halo config set` shows
// at once.
import { useEffect } from "react";
import { useStore } from "../store";
import { settings, startSettings, type Value } from "../../routes/settings/store";

export const HOVER_KEY = "studio.hover_cards";
export type HoverMode = "on" | "off" | "wait";

export function modeOf(v: Value | undefined, loaded: boolean): HoverMode {
  if (!v) return loaded ? "on" : "wait";
  return (v.set ? v.value : v.default) === false ? "off" : "on";
}

export function useHoverMode(): HoverMode {
  useEffect(() => startSettings(), []);
  return useStore(settings, (s) => modeOf(s.values[HOVER_KEY], s.loaded));
}
