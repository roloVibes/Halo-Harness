// Roles (3.0.7.0 R2; 3.3.16.0 R1: Agents' Cast and Live, routes/agents/): lineups and agent bios as React panels (the
// framed classic page is gone). Until you have a lineup of your own (and none
// is active) the section is the Start view (Start.tsx). Then six panels:
// Lineups (roles-lineups: the list, New, Duplicate, Delete, Apply), the
// canvas (roles-graph, its drawn canvas data-testid roles-canvas: cards
// in tier boxes, the edges, drag to move or to change a tier, Live Roles; 3.4.1.0 R1:
// the replay bar went to Live's scrubber), the Inspector (roles-inspector: Assignment, Lineup's
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
  const any = useRoles((s) => !!s.graph?.nodes.length);
  return live ? "working" : any ? "idle" : "none";
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

// 3.6.0.0 R0a, the stage: the Canvas is the main thing; Lineups and Bios open as left drawers, Inspector, Problems and
// Models as right ones (this view is redrawn in the rounds after R0a: no more than the mapping here).
export const rolesPanels: PanelSpec[] = [
  panel("roles-lineups", { title: "Lineups", side: "left", contentW: 360, face: "detail", glance: LineupsGlance, detail: LineupsDetail, useMotion: started(idle) }),
  panel("roles-bios", { title: "Bios", fullGrow: 2, side: "left", contentW: 440, face: "detail", glance: BiosGlance, detail: BiosDetail, useMotion: started(idle) }),
  panel("roles-graph", { title: "Canvas", primary: true, face: "detail", glance: CanvasGlance, detail: CanvasDetail, useMotion: started(useCanvasMotion) }),
  panel("roles-inspector", { title: "Inspector", fullGrow: 3, contentW: 400, face: "detail", glance: InspectorGlance, detail: InspectorDetail }),
  panel("roles-problems", { title: "Problems", contentW: 360, face: "detail", glance: ProblemsGlance, detail: ProblemsDetail, useMotion: started(useProblemsMotion) }),
  panel("roles-models", { title: "Models", contentW: 420, face: "detail", glance: ModelsGlance, detail: ModelsDetail }),
];
