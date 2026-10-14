// The section registry. A section is an id, a title, its Alt+N key, a one-
// line blurb and the PanelSpecs of its default arrangement; the Workspace
// does the rest (drag, resize, collapse, pop out, persistence). R4 replaces
// orchestraPanels; a new section is one more entry here.
import type { SectionId } from "../lib/store";
import type { PanelSpec } from "../lib/workspace/types";
import { legacyPanels } from "./legacy/LegacyFrame";
import { orchestraPanels } from "./orchestra/Orchestra";

export type SectionDef = { id: SectionId; title: string; kbd: string; blurb: string; panels: PanelSpec[] };

export const SECTIONS: SectionDef[] = [
  { id: "orchestra", title: "Orchestra", kbd: "Alt+1", blurb: "Runs of your agents, live", panels: orchestraPanels },
  { id: "roles", title: "Roles", kbd: "Alt+2", blurb: "Lineups and agent bios", panels: legacyPanels("roles", "Roles") },
  { id: "org", title: "Org", kbd: "Alt+3", blurb: "Your company in Paperclip", panels: legacyPanels("org", "Org") },
  { id: "design", title: "Design", kbd: "Alt+4", blurb: "Prototypes, pages and decks", panels: legacyPanels("design", "Design") },
];

export function sectionDef(id: SectionId): SectionDef {
  return SECTIONS.find((s) => s.id === id) ?? SECTIONS[0];
}
