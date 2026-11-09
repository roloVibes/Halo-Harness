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

export const designPanels: PanelSpec[] = [
  panel("design-projects", { title: "Projects", x: 0, y: 0, w: 5, h: 22, minW: 4, minH: 12, face: "detail", glance: ProjectsGlance, detail: ProjectsDetail, useMotion: started(useProjectsMotion) }),
  panel("design-system", { title: "Design system", x: 0, y: 22, w: 5, h: 34, minW: 4, minH: 12, face: "detail", glance: SystemGlance, detail: SystemDetail, useMotion: started(useSystemMotion) }),
  panel("design-assets", { title: "Assets", x: 0, y: 56, w: 5, h: 0, minW: 4, minH: 12, face: "detail", glance: AssetsGlance, detail: AssetsDetail, useMotion: started(() => "none") }),
  panel("design-artboards", { title: "Artboards", primary: true, x: 5, y: 0, w: 12, h: 0, minW: 8, minH: 24, face: "detail", glance: ArtboardsGlance, detail: ArtboardsDetail, settings: ArtboardsSettings, useMotion: started(useArtboardsMotion) }),
  panel("design-thread", { title: "Thread", x: 17, y: 0, w: 7, h: 0, minW: 5, minH: 24, face: "detail", glance: ThreadGlance, detail: ThreadDetail, useMotion: started(useThreadMotion) }),
  panel("design-render", { title: "Render", x: 0, y: 200, w: 12, h: 40, minW: 6, minH: 12, face: "detail", collapsed: true, glance: RenderGlance, detail: RenderDetail, useMotion: started(useRenderMotion) }),
  panel("design-settings", { title: "Settings", x: 12, y: 200, w: 12, h: 24, minW: 6, minH: 10, face: "detail", collapsed: true, glance: SettingsGlance, detail: SettingsDetail, useMotion: started(() => "none") }),
];
