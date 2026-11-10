// The section registry. A section is an id, a title, its Alt+N key, a one-
// line blurb, the PanelSpecs of its default arrangement and, optionally, a
// group of its own rows in the header's "+" menu (3.3.2.0 R2, Agents' Runs: New
// run and the runs; the rail's block before) and a view
// drawn instead of the bare Workspace (Agents: its bar and its three views;
// 3.1.4.0 R2 Session: until this harness has a live
// session). Every section is React now
// (the framed classic page is gone). The Workspace does the rest
// (drag, resize, collapse, pop out, persistence). Each section's "How this
// works" copy is routes/sectionHelp.ts.
// 3.1.6.0 R6: this list IS the order: the rail's section rows (3.3.2.0 R1; the tab strip before), the Alt+1..6 keys (shell/keys.ts), the palette's
// Go to and section groups, the section help's key line and the status bar's key hint all read it.
// The owner, 2026-10-20: "The session tab should be the first tab in studio".
// 3.2.0.0 R6: Packs (the Pack Manager) was appended, 3.3.0.0 R1 Setup (the terminal wizard's blocks as forms; 3.3.1.0 R1
// `paged`: a step rail over one page at a time, no panels), 3.3.3.0 R2 Settings (every config.json key, one page per
// group), 3.3.5.0 R1 Local (the machines that serve models, and the models they serve), each paged too.
// 3.3.13.0 R2: Design left the core for the design pack (its section, when the pack is on, is a pack section).
// 3.3.16.0 R1 "Agents: one section": Team, Roles and Orchestra folded into Agents (Alt+2; routes/agents/). Agents draws
// two workspaces of its own: `roles` (Cast and Live) and `orchestra` (Runs); `sectionDef("agents")` is the one it draws
// now (partDef), so the "+" menu, the ... menu, the palette's panel rows and the status bar follow the view. Local
// carries the Media panels as optional floating ones (its "+" menu).
// 3.3.16.0 R2 "the Fleet fold": the Fleet section went -- a machine's agents in Agents -> Live (the fleet scope), its
// models in Local, pairing and the people in Setup -> Machines, missions in Agents -> Runs. Six core sections, the shell
// the Instrument look was drawn for: Session Alt+1, Agents Alt+2, Local Alt+3, Packs Alt+4, Setup Alt+5,
// Settings Alt+6; then the pack sections (routes/packs/registry.ts FIRST_KEY: the first pack section is Alt+7).
import type { ComponentType } from "react";
import type { AgentsPart, SectionId } from "../lib/store";
import type { PanelSpec } from "../lib/workspace/types";
import { specsFor } from "../lib/workspace/persist";
import type { MenuGroup } from "../lib/ui/Menu";
import { AgentsView } from "./agents/Agents";
import { partPanels } from "./agents/parts";
import { agentsPart, useAgentsPart } from "./agents/store";
import { mediaPanels } from "./media/MediaPanels";
import { useOrchestraMenu } from "./orchestra/OrchRail";
import { enterWorkspace as enterOrchestra } from "./orchestra/store";
import { setView as enterRoles } from "./roles/store";
import { sessionPanels } from "./session/Session";
import { SessionView } from "./session/Start";
import { enterSession } from "./session/store";
import { packPanels, packSections } from "./packs/registry";
import { packs, usePacks } from "./packs/store";
import { enterPacks, packsPanels } from "./packs/manager/Manager";
import { enterSetup, SetupView } from "./setup/Setup";
import { enterSettings, SettingsView } from "./settings/Settings";
import { enterLocal, LocalView } from "./local/Local";

export type SectionDef = {
  id: SectionId;
  title: string;
  kbd: string;
  blurb: string;
  panels: PanelSpec[];
  /** 3.3.2.0 R2: a hook giving the section's own rows in the header's "+" menu, under its panels (Agents' Runs: the runs). */
  menu?: () => MenuGroup;
  /** Draws the section instead of the bare Workspace (Agents: its bar and its views). */
  view?: ComponentType<{ section: string; specs: PanelSpec[] }>;
  /** Brings the panel workspace up (before the "+" menu or the palette opens a panel). */
  enter?: () => void;
  /** 3.3.1.0 R1: pages, not panels (Setup): no "+" menu, no layout actions, the view is the room. 3.3.13.0 R2: a paged
   *  section's optional panels (Local: Media) are still in its "+" menu; each floats over the page. */
  paged?: boolean;
};

export const SECTIONS: SectionDef[] = [
  { id: "session", title: "Session", kbd: "Alt+1", blurb: "This session, live", panels: sessionPanels, view: SessionView, enter: enterSession },
  { id: "agents", title: "Agents", kbd: "Alt+2", blurb: "The cast, its runs, and what runs now on every machine", panels: [], view: AgentsView },
  { id: "local", title: "Local", kbd: "Alt+3", blurb: "The machines that serve models, and the models they serve", panels: mediaPanels(0), paged: true, view: LocalView, enter: enterLocal },
  { id: "packs", title: "Packs", kbd: "Alt+4", blurb: "Install, grant and enable packs", panels: packsPanels, enter: enterPacks },
  { id: "setup", title: "Setup", kbd: "Alt+5", blurb: "Providers, models, permissions, theme, lineup and machines", panels: [], paged: true, view: SetupView, enter: enterSetup },
  { id: "settings", title: "Settings", kbd: "Alt+6", blurb: "Every config key, one page per group", panels: [], paged: true, view: SettingsView, enter: enterSettings },
];

/** 3.3.16.0 R1: one of Agents' workspaces as a section def (its layout key is its id; the title and key are Agents'). */
const PARTS: Record<AgentsPart, Pick<SectionDef, "menu" | "enter">> = {
  roles: { enter: () => enterRoles("workspace") },
  orchestra: { menu: useOrchestraMenu, enter: enterOrchestra },
};

const AGENTS = SECTIONS[1];

export function partDef(part: AgentsPart): SectionDef {
  return { ...AGENTS, ...PARTS[part], id: part, panels: partPanels(packs.get().reg, part), view: undefined };
}

// 3.2.0.0 R3: the packs' sections come after the core ones (3.3.3.0 R2: after Settings, reached by a click or the palette;
// 3.3.16.0 R1: then the pack's own sections, by their rail row) and their panels join the core sections' (routes/packs/registry.ts, from the
// registry the server builds); SECTIONS stays the core six, in their order.
let merged: { reg: unknown; out: SectionDef[] } = { reg: null, out: SECTIONS };

/** Every section, the six core ones (with the packs' panels added) then the packs' own. */
export function sections(): SectionDef[] {
  const reg = packs.get().reg;
  if (merged.reg !== reg) {
    const core = SECTIONS.map((s) => {
      const extra = s.paged || s.id === "agents" ? [] : packPanels(reg, s.id); // a paged section draws no workspace for a pack's panel; Agents' parts take theirs
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
  if (id === "roles" || id === "orchestra") return partDef(id);
  if (id === "agents") return partDef(agentsPart()); // 3.3.16.0 R1: the workspace Agents draws now
  const def = sections().find((s) => s.id === id) ?? SECTIONS[0];
  // 3.3.13.0 R2: a pack's page with a Workspace of its own (api.lib.workspace): its panels, for the Inspector
  const own = def.view && def.paged && !def.panels.length ? specsFor(def.id) : undefined;
  return own?.length ? { ...def, panels: own } : def;
}

/** sectionDef, re-read when the packs registry or Agents' view changes (the "+" menu, the ... menu, the status bar). */
export function useSectionDef(id: SectionId): SectionDef {
  usePacks((s) => s.reg);
  useAgentsPart();
  return sectionDef(id);
}
