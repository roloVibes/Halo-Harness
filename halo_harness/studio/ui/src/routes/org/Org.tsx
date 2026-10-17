// Org (Alt+3, 3.0.7.0 R3): your company in Paperclip as React panels (the
// framed classic page is gone from here). Until a company is linked the
// section is the Start view (Start.tsx). Then four panels: Company
// (org-company: Paperclip installed / running / linked, Org mode, Install,
// Link, Sync, Pull), the chart (org-chart, its drawn canvas data-testid
// org-canvas: the agents in group boxes, reports-to lines, drag to move or
// to change a manager), the work lists
// (org-work: issues, goals, projects) and the Inspector (org-inspector: the
// agent, issue, goal or project clicked). One store (store.ts), fed by one
// diffed 3 s poller while Org shows (sync.ts).
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { CanvasDetail, CanvasGlance, useCanvasMotion } from "./Canvas";
import { CompanyDetail, CompanyGlance, useCompanyMotion } from "./Company";
import { InspectorDetail, InspectorGlance } from "./Inspector";
import { startOrg } from "./sync";
import { WorkDetail, WorkGlance, useWorkMotion } from "./Work";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startOrg(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest });

export const orgPanels: PanelSpec[] = [
  panel("org-company", { title: "Company", x: 0, y: 0, w: 6, h: 34, minW: 4, minH: 12, face: "detail", glance: CompanyGlance, detail: CompanyDetail, useMotion: started(useCompanyMotion) }),
  panel("org-work", { title: "Issues, goals, projects", x: 0, y: 34, w: 6, h: 0, minW: 4, minH: 16, face: "detail", glance: WorkGlance, detail: WorkDetail, useMotion: started(useWorkMotion) }),
  panel("org-chart", { title: "Org chart", x: 6, y: 0, w: 12, h: 0, minW: 8, minH: 24, face: "detail", glance: CanvasGlance, detail: CanvasDetail, useMotion: started(useCanvasMotion) }),
  panel("org-inspector", { title: "Inspector", x: 18, y: 0, w: 6, h: 0, minW: 4, minH: 16, face: "detail", glance: InspectorGlance, detail: InspectorDetail }),
];
