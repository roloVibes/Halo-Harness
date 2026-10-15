// The section registry. A section is an id, a title, its Alt+N key, a one-
// line blurb, the PanelSpecs of its default arrangement and, optionally, a
// block the rail shows above its panels (Orchestra: the runs; Flow: the runs
// and the flows) and a view drawn instead of the bare Workspace (Orchestra
// and Flow: the Start view until a run is open; Fleet: until something runs). The Workspace does the rest
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
import { legacyPanels } from "./legacy/LegacyFrame";
import { mediaPanels } from "./media/MediaPanels";
import { orchestraPanels } from "./orchestra/Orchestra";
import { OrchestraRail } from "./orchestra/OrchRail";
import { OrchestraView } from "./orchestra/Start";
import { enterWorkspace as enterOrchestra } from "./orchestra/store";

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
  { id: "roles", title: "Roles", kbd: "Alt+2", blurb: "Lineups and agent bios", panels: legacyPanels("roles", "Roles") },
  { id: "org", title: "Org", kbd: "Alt+3", blurb: "Your company in Paperclip", panels: legacyPanels("org", "Org") },
  { id: "design", title: "Design", kbd: "Alt+4", blurb: "Prototypes, pages and decks", panels: [...legacyPanels("design", "Design"), ...mediaPanels(0, "optional")] },
  { id: "flow", title: "Flow", kbd: "Alt+5", blurb: "A brief to renders, posts and metrics", panels: flowPanels, rail: FlowRail, view: FlowView, enter: enterWorkspace },
  { id: "fleet", title: "Fleet", kbd: "Alt+6", blurb: "Every harness, every agent, live", panels: fleetPanels, view: FleetView, enter: enterFleet },
];

export function sectionDef(id: SectionId): SectionDef {
  return SECTIONS.find((s) => s.id === id) ?? SECTIONS[0];
}
