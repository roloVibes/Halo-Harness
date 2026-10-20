// Roles (Alt+3, 3.0.7.0 R2): lineups and agent bios as React panels (the
// framed classic page is gone). Until you have a lineup of your own (and none
// is active) the section is the Start view (Start.tsx). Then six panels:
// Lineups (roles-lineups: the list, New, Duplicate, Delete, Apply), the
// canvas (roles-graph, its drawn canvas data-testid roles-canvas: cards
// in tier boxes, the edges, drag to move or to change a tier, Live Roles and
// the replay bar), the Inspector (roles-inspector: Assignment, Lineup's
// section forms, Live), Problems (roles-problems: blocks and warns from every
// edit), Bios (roles-bios: the list and the bio form with the model picker
// and "Test this model") and Models (roles-models: the catalog and Refresh).
// One store (store.ts), fed by sync.ts; the live agents come from the Fleet
// store (routes/fleet/frames.ts).
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { BiosDetail, BiosGlance } from "./Bios";
import { CanvasDetail } from "./Canvas";
import { InspectorDetail, InspectorGlance } from "./Inspector";
import { LineupsDetail, LineupsGlance } from "./Lineups";
import { useByNode } from "./live";
import { ModelsDetail, ModelsGlance } from "./Models";
import { ProblemsDetail, ProblemsGlance, useProblemsMotion } from "./Problems";
import { useRoles } from "./store";
import { startRoles } from "./sync";
import { Metric } from "../orchestra/bits";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startRoles(), []);
    return hook();
  };
}

function useCanvasMotion(): MotionState {
  const live = Object.keys(useByNode()).length > 0;
  const replay = useRoles((s) => !!s.replay);
  const any = useRoles((s) => !!s.graph?.nodes.length);
  return live || replay ? "working" : any ? "idle" : "none";
}

function CanvasGlance() {
  const n = useRoles((s) => s.graph?.nodes.length || 0);
  const tiers = useRoles((s) => s.graph?.tiers.length || 0);
  const live = Object.keys(useByNode()).length;
  return (
    <div className="glance">
      <div className="glance-numbers">
        <Metric value={n} label="cards" />
        <Metric value={tiers} label="tiers" />
        <Metric value={live} label="live" tone={live ? "accent" : undefined} />
      </div>
      <div className="glance-hint">Expand for the canvas: one box per tier.</div>
    </div>
  );
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest });
const idle = () => "idle" as MotionState;

export const rolesPanels: PanelSpec[] = [
  panel("roles-lineups", { title: "Lineups", x: 0, y: 0, w: 5, h: 32, minW: 4, minH: 12, face: "detail", glance: LineupsGlance, detail: LineupsDetail, useMotion: started(idle) }),
  panel("roles-bios", { title: "Bios", x: 0, y: 32, w: 5, h: 0, minW: 4, minH: 16, face: "detail", glance: BiosGlance, detail: BiosDetail, useMotion: started(idle) }),
  panel("roles-graph", { title: "Canvas", x: 5, y: 0, w: 13, h: 0, minW: 8, minH: 24, face: "detail", glance: CanvasGlance, detail: CanvasDetail, useMotion: started(useCanvasMotion) }),
  panel("roles-inspector", { title: "Inspector", x: 18, y: 0, w: 6, h: 46, minW: 4, minH: 16, face: "detail", glance: InspectorGlance, detail: InspectorDetail }),
  panel("roles-problems", { title: "Problems", x: 18, y: 46, w: 6, h: 20, minW: 4, minH: 10, face: "detail", glance: ProblemsGlance, detail: ProblemsDetail, useMotion: started(useProblemsMotion) }),
  panel("roles-models", { title: "Models", x: 18, y: 66, w: 6, h: 0, minW: 4, minH: 10, face: "detail", glance: ModelsGlance, detail: ModelsDetail }),
];
