// Design (Alt+5, 3.0.7.0 R3): prototypes, pages and decks as React panels
// (the framed classic page is gone from here). Until a project exists the
// section is the Start view (Start.tsx). Then: Projects (design-projects),
// the Thread (design-thread: the turns as a markdown thread, the Send box,
// Cancel turn, 3 directions), the Artboards canvas (design-artboards:
// versions, restore, critique, contrast, rename, delete, download, Export,
// Handoff, the places saved on the server; R3b: pins, direct text edits,
// the device select, and the knobs in its settings face), the design system
// (design-system, R3b: tokens and Sync) and Assets (design-assets). The
// Media panels stay optional ones the palette adds. One store (store.ts),
// fed by sync.ts: turns over the live feed, the poll only when the feed is
// down; edit.ts listens for the frames' double-clicks.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ArtboardsDetail, ArtboardsGlance, useArtboardsMotion } from "./Artboards";
import { AssetsDetail, AssetsGlance } from "./Assets";
import { listenEdits } from "./edit";
import { DESIGN_MORE_HELP } from "./help";
import { ArtboardsSettings } from "./Knobs";
import { ProjectsDetail, ProjectsGlance, useProjectsMotion } from "./Projects";
import { startDesign } from "./sync";
import { SystemDetail, SystemGlance, useSystemMotion } from "./System";
import { ThreadDetail, ThreadGlance, useThreadMotion } from "./Thread";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => (listenEdits(), startDesign()), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...DESIGN_MORE_HELP[id], ...rest });

export const designPanels: PanelSpec[] = [
  panel("design-projects", { title: "Projects", x: 0, y: 0, w: 5, h: 22, minW: 4, minH: 12, face: "detail", glance: ProjectsGlance, detail: ProjectsDetail, useMotion: started(useProjectsMotion) }),
  panel("design-system", { title: "Design system", x: 0, y: 22, w: 5, h: 34, minW: 4, minH: 12, face: "detail", glance: SystemGlance, detail: SystemDetail, useMotion: started(useSystemMotion) }),
  panel("design-assets", { title: "Assets", x: 0, y: 56, w: 5, h: 0, minW: 4, minH: 12, face: "detail", glance: AssetsGlance, detail: AssetsDetail, useMotion: started(() => "none") }),
  panel("design-artboards", { title: "Artboards", x: 5, y: 0, w: 12, h: 0, minW: 8, minH: 24, face: "detail", glance: ArtboardsGlance, detail: ArtboardsDetail, settings: ArtboardsSettings, useMotion: started(useArtboardsMotion) }),
  panel("design-thread", { title: "Thread", x: 17, y: 0, w: 7, h: 0, minW: 5, minH: 24, face: "detail", glance: ThreadGlance, detail: ThreadDetail, useMotion: started(useThreadMotion) }),
];
