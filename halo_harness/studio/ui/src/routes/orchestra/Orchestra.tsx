// Orchestra: the run console. Before a run is open the section is one Start
// view (Start.tsx); then eight panels on the movable workspace, each opening
// on its full face (Workflow, Run grid and Log on their compact one, which
// is the whole graph, every tile and the newest lines at the default size),
// with its `about` line and `help` (help-orchestra.ts): Goal, Workflow, Run
// grid, Live file, Lanes, Report, Claims, Log. The Goal panel's default
// height fits every field and Run. One store (store.ts) fed by GET
// orchestra/<run> and the live feed's orchestra_* frames (sync.ts); the
// first panel that mounts starts it.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ClaimsDetail, ClaimsGlance, useClaimsMotion } from "./Claims";
import { GoalDetail, GoalGlance, GoalSettings, useGoalMotion } from "./GoalPanel";
import { LanesDetail, LanesGlance, LanesSettings, useLanesMotion } from "./Lanes";
import { LiveFileDetail, LiveFileGlance, LiveFileSettings, useLiveFileMotion } from "./LiveFile";
import { LogDetail, LogGlance, LogSettings, useLogMotion } from "./Log";
import { ReportDetail, ReportGlance, ReportSettings, useReportMotion } from "./Report";
import { RunGridDetail, RunGridGlance, useGridMotion } from "./RunGrid";
import { startOrchestra } from "./sync";
import { GraphDetail, GraphGlance, GraphSettings, useGraphMotion } from "./WorkflowGraph";

/** A panel's motion hook that also starts the store's feed (once). */
function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startOrchestra(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id">): PanelSpec => ({ id, ...HELP[id], ...rest });

// 24 columns, 8 px rows; h 0 fills the visible height (98 rows in a 900 px window). 3.1.4.0 R4:
// the Goal panel is 12 rows taller for its MODEL select, so every field and Run still fit.
export const orchestraPanels: PanelSpec[] = [
  panel("goal", { title: "Goal", x: 0, y: 0, w: 6, h: 78, minW: 5, minH: 40, glance: GoalGlance, detail: GoalDetail, settings: GoalSettings, useMotion: started(useGoalMotion), testid: "orchestra-root" }),
  panel("graph", { title: "Workflow", primary: true, x: 6, y: 0, w: 12, h: 30, minW: 8, minH: 16, face: "glance", glance: GraphGlance, detail: GraphDetail, settings: GraphSettings, useMotion: started(useGraphMotion) }),
  panel("grid", { title: "Run grid", x: 18, y: 0, w: 6, h: 30, minW: 4, minH: 14, face: "glance", glance: RunGridGlance, detail: RunGridDetail, useMotion: started(useGridMotion) }),
  panel("file", { title: "Live file", x: 6, y: 30, w: 8, h: 0, minW: 6, minH: 20, glance: LiveFileGlance, detail: LiveFileDetail, settings: LiveFileSettings, useMotion: started(useLiveFileMotion) }),
  panel("lanes", { title: "Lanes", x: 14, y: 30, w: 10, h: 34, minW: 6, minH: 14, glance: LanesGlance, detail: LanesDetail, settings: LanesSettings, useMotion: started(useLanesMotion) }),
  panel("report", { title: "Report", x: 14, y: 64, w: 5, h: 0, minW: 4, minH: 14, glance: ReportGlance, detail: ReportDetail, settings: ReportSettings, useMotion: started(useReportMotion) }),
  panel("claims", { title: "Claims", x: 19, y: 64, w: 5, h: 0, minW: 4, minH: 12, glance: ClaimsGlance, detail: ClaimsDetail, useMotion: started(useClaimsMotion) }),
  panel("log", { title: "Log", x: 0, y: 78, w: 6, h: 0, minW: 5, minH: 14, face: "glance", glance: LogGlance, detail: LogDetail, settings: LogSettings, useMotion: started(useLogMotion) }),
];
