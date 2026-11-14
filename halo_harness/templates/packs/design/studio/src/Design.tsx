// Design (3.0.7.0 R3; the design pack's page since 3.3.13.0 R2): prototypes, pages and decks as React panels on the
// shell's own workspace. Until a project exists the page is the Start view (Start.tsx). Then: Projects
// (design-projects), the Thread (design-thread: the turns as a markdown thread, the Send box, Cancel turn,
// 3 directions), the Artboards canvas (design-artboards: versions, restore, critique, contrast, rename, delete,
// download, Export, Handoff, the places saved on the server; R3b: pins, direct text edits, the device select, and the
// knobs in its settings face), the design system (design-system, R3b: tokens and Sync), Assets (design-assets), and
// (3.3.13.0 R2) Render (a ComfyUI workflow into the project: the core's Media render before) and Settings (the pack's
// own, PackForm over its config.schema), both strips at the foot. One store (store.ts), fed by sync.ts: turns over
// the live feed, the poll only when the feed is down; edit.ts listens for the frames' double-clicks.
import { useEffect } from "react";
import { PackForm } from "@halo/widgets";
import type { MotionState, PanelSpec } from "@halo/workspace";
import { ArtboardsDetail, ArtboardsGlance, useArtboardsMotion } from "./Artboards";
import { AssetsDetail, AssetsGlance } from "./Assets";
import { PACK } from "./base";
import { listenEdits } from "./edit";
import { DESIGN_MORE_HELP } from "./help";
import { DESIGN_HELP } from "./help-panels";
import { ArtboardsSettings } from "./Knobs";
import { ProjectsDetail, ProjectsGlance, useProjectsMotion } from "./Projects";
import { RenderDetail, RenderGlance, useRenderMotion } from "./Render";
import { startDesign } from "./sync";
import { SystemDetail, SystemGlance, useSystemMotion } from "./System";
import { ThreadDetail, ThreadGlance, useThreadMotion } from "./Thread";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => (listenEdits(), startDesign()), []);
    return hook();
  };
}

function SettingsDetail() {
  return <PackForm p={{ pack: PACK }} />;
}

function SettingsGlance() {
  return <div className="glance"><div className="glance-text">The model a new project starts with, a turn's cap.</div></div>;
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...DESIGN_HELP[id], ...DESIGN_MORE_HELP[id], ...rest });

// 3.6.0.0 R0a, the stage: Artboards is the main thing; Projects, Design system and Assets open as left drawers, the
// Thread, Render and Settings as right ones (their buttons in the view bar).
export const designPanels: PanelSpec[] = [
  panel("design-projects", { title: "Projects", side: "left", contentW: 360, face: "detail", glance: ProjectsGlance, detail: ProjectsDetail, useMotion: started(useProjectsMotion) }),
  panel("design-system", { title: "Design system", side: "left", contentW: 360, face: "detail", glance: SystemGlance, detail: SystemDetail, useMotion: started(useSystemMotion) }),
  panel("design-assets", { title: "Assets", side: "left", contentW: 360, face: "detail", glance: AssetsGlance, detail: AssetsDetail, useMotion: started(() => "none") }),
  panel("design-artboards", { title: "Artboards", primary: true, face: "detail", glance: ArtboardsGlance, detail: ArtboardsDetail, settings: ArtboardsSettings, useMotion: started(useArtboardsMotion) }),
  panel("design-thread", { title: "Thread", contentW: 420, face: "detail", glance: ThreadGlance, detail: ThreadDetail, useMotion: started(useThreadMotion) }),
  panel("design-render", { title: "Render", contentW: 480, face: "detail", collapsed: true, glance: RenderGlance, detail: RenderDetail, useMotion: started(useRenderMotion) }),
  panel("design-settings", { title: "Settings", contentW: 400, face: "detail", collapsed: true, glance: SettingsGlance, detail: SettingsDetail, useMotion: started(() => "none") }),
];
