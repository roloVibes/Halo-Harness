// The section registry. A section is an id, a title, its Alt+N key, a one-
// line blurb, the PanelSpecs of its default arrangement and, optionally, a
// block the rail shows above its panels (Orchestra: the runs) and a view
// drawn instead of the bare Workspace (Orchestra: the Start view until a run
// is open; Fleet: until something runs;
// 3.0.7.0 R3 Design: until a project exists;
// R2 Roles: until you have a lineup of your own; 3.0.8.0 R2 Team: until the
// team file loads clean; 3.1.4.0 R2 Session: until this harness has a live
// session -- its panels are Fleet's, scoped to this harness). Every section is React now
// (the framed classic page is gone). The Workspace does the rest
// (drag, resize, collapse, pop out, persistence). Each section's "How this
// works" copy is routes/sectionHelp.ts.
// Design also carries the Media panels as optional ones the palette adds.
// 3.1.6.0 R6: this list IS the order: the tab strip, the Alt+1..7 keys (shell/keys.ts), the palette's
// Go to and section groups, the section help's key line and the status bar's key hint all read it.
// The owner, 2026-10-20: "The session tab should be the first tab in studio", then "Here's the order of
// tabs in studio: session, team, roles, fleet, design"; Orchestra, not in his list, takes the next key.
// 3.2.0.0 R6: Packs (the Pack Manager) is appended as the seventh core section, Alt+7; the six keep theirs.
import type { ComponentType } from "react";
import type { SectionId } from "../lib/store";
import type { PanelSpec } from "../lib/workspace/types";
import { fleetPanels } from "./fleet/Fleet";
import { FleetView } from "./fleet/Start";
import { enterWorkspace as enterFleet } from "./fleet/store";
import { designPanels } from "./design/Design";
import { DesignView } from "./design/Start";
import { mediaPanels } from "./media/MediaPanels";
import { orchestraPanels } from "./orchestra/Orchestra";
import { OrchestraRail } from "./orchestra/OrchRail";
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
import { setView as enterTeam } from "./team/store";

export type SectionDef = {
  id: SectionId;
  title: string;
  kbd: string;
  blurb: string;
  panels: PanelSpec[];
  /** A block the rail shows above the panel list. */
  rail?: ComponentType;
  /** Draws the section instead of the bare Workspace (Orchestra: its Start view first). */
  view?: ComponentType<{ section: string; specs: PanelSpec[] }>;
  /** Brings the panel workspace up (before the rail or the palette opens a panel). */
  enter?: () => void;
};

export const SECTIONS: SectionDef[] = [
  { id: "session", title: "Session", kbd: "Alt+1", blurb: "This session, live", panels: sessionPanels, view: SessionView, enter: enterSession },
  { id: "team", title: "Team", kbd: "Alt+2", blurb: "People, blocks and stages on one board", panels: teamPanels, view: TeamView, enter: () => enterTeam("workspace") },
  { id: "roles", title: "Roles", kbd: "Alt+3", blurb: "Lineups and agent bios", panels: rolesPanels, view: RolesView, enter: () => enterRoles("workspace") },
  { id: "fleet", title: "Fleet", kbd: "Alt+4", blurb: "Every harness, every agent, live", panels: fleetPanels, view: FleetView, enter: enterFleet },
  { id: "design", title: "Design", kbd: "Alt+5", blurb: "Prototypes, pages and decks", panels: [...designPanels, ...mediaPanels(0)], view: DesignView },
  { id: "orchestra", title: "Orchestra", kbd: "Alt+6", blurb: "Runs of your agents, live", panels: orchestraPanels, rail: OrchestraRail, view: OrchestraView, enter: enterOrchestra },
  { id: "packs", title: "Packs", kbd: "Alt+7", blurb: "Install, grant and enable packs", panels: packsPanels, enter: enterPacks },
];

// 3.2.0.0 R3: the packs' sections come after the core ones (3.2.0.0 R6: after Packs, Alt+8 and Alt+9) and their
// panels join the core sections' (routes/packs/registry.ts, from the registry the server builds); SECTIONS stays the core seven, in their order.
let merged: { reg: unknown; out: SectionDef[] } = { reg: null, out: SECTIONS };

/** Every section, the seven core ones (with the packs' panels added) then the packs' own. */
export function sections(): SectionDef[] {
  const reg = packs.get().reg;
  if (merged.reg !== reg) {
    const core = SECTIONS.map((s) => {
      const extra = packPanels(reg, s.id);
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
  return sections().find((s) => s.id === id) ?? SECTIONS[0];
}
