// The section registry. A section is an id, a title, its Alt+N key, a one-
// line blurb, the PanelSpecs of its default arrangement and, optionally, a
// block the rail shows above its panels (Orchestra: the runs; Flow: the runs
// and the flows) and a view drawn instead of the bare Workspace (Orchestra
// and Flow: the Start view until a run is open; Fleet: until something runs;
// 3.0.7.0 R3 Org: until a company is linked, Design: until a project exists;
// R2 Roles: until you have a lineup of your own). Every section is React now
// (the framed classic page is gone). The Workspace does the rest
// (drag, resize, collapse, pop out, persistence). Each section's "How this
// works" copy is routes/sectionHelp.ts.
// Design also carries the Media panels as optional ones the palette adds.
import type { ComponentType } from "react";
import type { SectionId } from "../lib/store";
import type { PanelSpec } from "../lib/workspace/types";
import { flowPanels } from "./flow/Flow";
import { FlowRail } from "./flow/FlowRail";
import { FlowView } from "./flow/Start";
import { enterWorkspace } from "./flow/store";
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
import { orgPanels } from "./org/Org";
import { OrgView } from "./org/Start";
import { setView as enterOrg } from "./org/store";
import { rolesPanels } from "./roles/Roles";
import { RolesView } from "./roles/Start";
import { setView as enterRoles } from "./roles/store";

export type SectionDef = {
  id: SectionId;
  title: string;
  kbd: string;
  blurb: string;
  panels: PanelSpec[];
  /** A block the rail shows above the panel list. */
  rail?: ComponentType;
  /** Draws the section instead of the bare Workspace (Flow: its Start view first). */
  view?: ComponentType<{ section: string; specs: PanelSpec[] }>;
  /** Brings the panel workspace up (before the rail or the palette opens a panel). */
  enter?: () => void;
};

export const SECTIONS: SectionDef[] = [
  { id: "orchestra", title: "Orchestra", kbd: "Alt+1", blurb: "Runs of your agents, live", panels: orchestraPanels, rail: OrchestraRail, view: OrchestraView, enter: enterOrchestra },
  { id: "roles", title: "Roles", kbd: "Alt+2", blurb: "Lineups and agent bios", panels: rolesPanels, view: RolesView, enter: () => enterRoles("workspace") },
  { id: "org", title: "Org", kbd: "Alt+3", blurb: "Your company in Paperclip", panels: orgPanels, view: OrgView, enter: () => enterOrg("workspace") },
  { id: "design", title: "Design", kbd: "Alt+4", blurb: "Prototypes, pages and decks", panels: [...designPanels, ...mediaPanels(0, "optional")], view: DesignView },
  { id: "flow", title: "Flow", kbd: "Alt+5", blurb: "A brief to renders, posts and metrics", panels: flowPanels, rail: FlowRail, view: FlowView, enter: enterWorkspace },
  { id: "fleet", title: "Fleet", kbd: "Alt+6", blurb: "Every harness, every agent, live", panels: fleetPanels, view: FleetView, enter: enterFleet },
];

export function sectionDef(id: SectionId): SectionDef {
  return SECTIONS.find((s) => s.id === id) ?? SECTIONS[0];
}
