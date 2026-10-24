// Packs (Alt+7, 3.2.0.0 R6): the Pack Manager, Studio's seventh core section.
// Five panels over one store (store.ts, `GET pack/manager`, redrawn on every
// `pack_changed`): Installed (every pack here and its actions), Sources
// (packs.sources and the packs Halo ships, with Install), Details (the
// selected pack: ranges, dependencies, compatibility, the Grant toggles, what
// it contributes, its health), Settings (R3's form, any installed pack) and
// Templates (its lineups and bios with R2's Roles actions, its workflows with
// Run). Layout at 1440x900: Installed and Details side by side on top, the
// other three in a row under them.
import { useEffect } from "react";
import type { MotionState } from "../../../lib/motion";
import type { PanelSpec } from "../../../lib/workspace/types";
import { HELP } from "../../help";
import { DetailsDetail, DetailsGlance } from "./Details";
import { InstalledDetail, InstalledGlance } from "./Installed";
import { SettingsDetail, SettingsGlance } from "./Settings";
import { SourcesDetail, SourcesGlance } from "./Sources";
import { startManager, useMgr } from "./store";
import { TemplatesDetail, TemplatesGlance } from "./Templates";

function useManagerMotion(): MotionState {
  useEffect(() => startManager(), []);
  return useMgr((s) => (s.busy ? "working" : "none"));
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest, useMotion: useManagerMotion });

export const packsPanels: PanelSpec[] = [
  panel("pm-installed", { title: "Installed", x: 0, y: 0, w: 13, h: 46, minW: 6, minH: 12, face: "detail", glance: InstalledGlance, detail: InstalledDetail }),
  panel("pm-details", { title: "Details", x: 13, y: 0, w: 11, h: 46, minW: 6, minH: 12, face: "detail", glance: DetailsGlance, detail: DetailsDetail }),
  panel("pm-sources", { title: "Sources", x: 0, y: 46, w: 9, h: 0, minW: 6, minH: 10, face: "detail", glance: SourcesGlance, detail: SourcesDetail }),
  panel("pm-settings", { title: "Settings", x: 9, y: 46, w: 6, h: 0, minW: 4, minH: 10, face: "detail", glance: SettingsGlance, detail: SettingsDetail }),
  panel("pm-templates", { title: "Templates", x: 15, y: 46, w: 9, h: 0, minW: 6, minH: 10, face: "detail", glance: TemplatesGlance, detail: TemplatesDetail }),
];

/** The section's entry: the manager's first read (the palette or the rail may open a panel before one draws). */
export function enterPacks(): void {
  startManager();
}
