// The section registry. A section is an id, a title, its Alt+N key, a one-
// line blurb, the PanelSpecs of its default arrangement and, optionally, a
// group of its own rows in the header's "+" menu (3.3.2.0 R2, Orchestra: New
// run and the runs; the rail's block before) and a view
// drawn instead of the bare Workspace (Orchestra: the Start view until a run
// is open; Fleet: until something runs;
// R2 Roles: until you have a lineup of your own; 3.0.8.0 R2 Team: until the
// team file loads clean; 3.1.4.0 R2 Session: until this harness has a live
// session -- its panels are Fleet's, scoped to this harness). Every section is React now
// (the framed classic page is gone). The Workspace does the rest
// (drag, resize, collapse, pop out, persistence). Each section's "How this
// works" copy is routes/sectionHelp.ts.
// 3.1.6.0 R6: this list IS the order: the rail's section rows (3.3.2.0 R1; the tab strip before), the Alt+1..9 keys (shell/keys.ts), the palette's
// Go to and section groups, the section help's key line and the status bar's key hint all read it.
// The owner, 2026-10-20: "The session tab should be the first tab in studio", then "Here's the order of
// tabs in studio: session, team, roles, fleet, design"; Orchestra, not in his list, takes the next key.
// 3.2.0.0 R6: Packs (the Pack Manager) was appended, 3.3.0.0 R1 Setup (the terminal wizard's blocks as forms; 3.3.1.0 R1
// `paged`: a step rail over one page at a time, no panels), 3.3.3.0 R2 Settings (every config.json key, one page per
// group), 3.3.5.0 R1 Local (the machines that serve models, and the models they serve), each paged too.
// 3.3.13.0 R2: Design left the core for the design pack (its section, when the pack is on, is the first pack section,
// on the design pack's key Alt+0): nine core sections, the keys after Fleet one up: Orchestra Alt+5, Packs Alt+6,
// Setup Alt+7, Settings Alt+8, Local Alt+9. Local carries the Media panels as optional floating ones (its "+" menu).
import type { ComponentType } from "react";
import type { SectionId } from "../lib/store";
import type { PanelSpec } from "../lib/workspace/types";
import { specsFor } from "../lib/workspace/persist";
import type { MenuGroup } from "../lib/ui/Menu";
import { fleetPanels } from "./fleet/Fleet";
import { FleetView } from "./fleet/Start";
import { enterWorkspace as enterFleet } from "./fleet/store";
import { mediaPanels } from "./media/MediaPanels";
import { orchestraPanels } from "./orchestra/Orchestra";
import { useOrchestraMenu } from "./orchestra/OrchRail";
import { OrchestraView } from "./orchestra/Start";
import { enterWorkspace as enterOrchestra } from "./orchestra/store";
import { rolesPanels } from "./roles/Roles";
import { RolesView } from "./roles/Start";
import { setView as enterRoles } from "./roles/store";
import { sessionPanels } from "./session/Session";
import { SessionView } from "./session/Start";
import { enterSession } from "./session/store";
import { teamPanels } from "./team/Team";
import { packPanels, packSections } from "./packs/registry";
import { packs, usePacks } from "./packs/store";
import { enterPacks, packsPanels } from "./packs/manager/Manager";
import { TeamView } from "./team/Start";
import { enterSetup, SetupView } from "./setup/Setup";
import { enterSettings, SettingsView } from "./settings/Settings";
import { enterLocal, LocalView } from "./local/Local";
import { setView as enterTeam } from "./team/store";

export type SectionDef = {
  id: SectionId;
  title: string;
  kbd: string;
  blurb: string;
  panels: PanelSpec[];
  /** 3.3.2.0 R2: a hook giving the section's own rows in the header's "+" menu, under its panels (Orchestra: the runs). */
  menu?: () => MenuGroup;
  /** Draws the section instead of the bare Workspace (Orchestra: its Start view first). */
  view?: ComponentType<{ section: string; specs: PanelSpec[] }>;
  /** Brings the panel workspace up (before the "+" menu or the palette opens a panel). */
  enter?: () => void;
  /** 3.3.1.0 R1: pages, not panels (Setup): no "+" menu, no layout actions, the view is the room. 3.3.13.0 R2: a paged
   *  section's optional panels (Local: Media) are still in its "+" menu; each floats over the page. */
  paged?: boolean;
};

export const SECTIONS: SectionDef[] = [
  { id: "session", title: "Session", kbd: "Alt+1", blurb: "This session, live", panels: sessionPanels, view: SessionView, enter: enterSession },
  { id: "team", title: "Team", kbd: "Alt+2", blurb: "People, blocks and stages on one board", panels: teamPanels, view: TeamView, enter: () => enterTeam("workspace") },
  { id: "roles", title: "Roles", kbd: "Alt+3", blurb: "Lineups and agent bios", panels: rolesPanels, view: RolesView, enter: () => enterRoles("workspace") },
  { id: "fleet", title: "Fleet", kbd: "Alt+4", blurb: "Every harness, every agent, live", panels: fleetPanels, view: FleetView, enter: enterFleet },
  { id: "orchestra", title: "Orchestra", kbd: "Alt+5", blurb: "Runs of your agents, live", panels: orchestraPanels, menu: useOrchestraMenu, view: OrchestraView, enter: enterOrchestra },
  { id: "packs", title: "Packs", kbd: "Alt+6", blurb: "Install, grant and enable packs", panels: packsPanels, enter: enterPacks },
  { id: "setup", title: "Setup", kbd: "Alt+7", blurb: "Providers, models, permissions, theme and lineup", panels: [], paged: true, view: SetupView, enter: enterSetup },
  { id: "settings", title: "Settings", kbd: "Alt+8", blurb: "Every config key, one page per group", panels: [], paged: true, view: SettingsView, enter: enterSettings },
  { id: "local", title: "Local", kbd: "Alt+9", blurb: "The machines that serve models, and the models they serve", panels: mediaPanels(0), paged: true, view: LocalView, enter: enterLocal },
];

// 3.2.0.0 R3: the packs' sections come after the core ones (3.3.3.0 R2: after Settings, reached by a click or the palette;
// 3.3.13.0 R2: the first pack section takes Alt+0) and their panels join the core sections' (routes/packs/registry.ts, from the
// registry the server builds); SECTIONS stays the core nine, in their order.
let merged: { reg: unknown; out: SectionDef[] } = { reg: null, out: SECTIONS };

/** Every section, the nine core ones (with the packs' panels added) then the packs' own. */
export function sections(): SectionDef[] {
  const reg = packs.get().reg;
  if (merged.reg !== reg) {
    const core = SECTIONS.map((s) => {
      const extra = s.paged ? [] : packPanels(reg, s.id); // a paged section draws no workspace for a pack's panel
      return extra.length ? { ...s, panels: [...s.panels, ...extra] } : s;
    });
    merged = { reg, out: [...core, ...packSections(reg)] };
  }
  return merged.out;
}

/** The same, re-read when the packs registry changes. */
export function useSections(): SectionDef[] {
  usePacks((s) => s.reg);
  return sections();
}

export function sectionDef(id: SectionId): SectionDef {
  const def = sections().find((s) => s.id === id) ?? SECTIONS[0];
  // 3.3.13.0 R2: a pack's page with a Workspace of its own (api.lib.workspace): its panels, for the Inspector
  const own = def.view && def.paged && !def.panels.length ? specsFor(def.id) : undefined;
  return own?.length ? { ...def, panels: own } : def;
}
