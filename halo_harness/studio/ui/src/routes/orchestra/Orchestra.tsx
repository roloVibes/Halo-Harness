// Orchestra: the run console. Eight panels on the movable workspace, each
// with a Glance face (what it is, one live indicator, one or two big
// numbers), an Expand face (the details) and Settings (the gear): Goal,
// Workflow, Run grid, Lanes, Live file, Report, Log, Claims. One store
// (store.ts) fed by GET orchestra/<run> and the live feed's orchestra_*
// frames (sync.ts); the first panel that mounts starts it.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
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

export const orchestraPanels: PanelSpec[] = [
  {
    id: "goal",
    title: "Goal",
    x: 0,
    y: 0,
    w: 6,
    h: 32,
    minW: 5,
    minH: 16,
    glance: GoalGlance,
    detail: GoalDetail,
    settings: GoalSettings,
    useMotion: started(useGoalMotion),
    testid: "orchestra-root",
  },
  {
    id: "graph",
    title: "Workflow",
    x: 6,
    y: 0,
    w: 12,
    h: 32,
    minW: 8,
    minH: 16,
    glance: GraphGlance,
    detail: GraphDetail,
    settings: GraphSettings,
    useMotion: started(useGraphMotion),
  },
  {
    id: "grid",
    title: "Run grid",
    x: 18,
    y: 0,
    w: 6,
    h: 32,
    minW: 4,
    minH: 14,
    glance: RunGridGlance,
    detail: RunGridDetail,
    useMotion: started(useGridMotion),
  },
  {
    id: "lanes",
    title: "Lanes",
    x: 0,
    y: 32,
    w: 10,
    h: 34,
    minW: 6,
    minH: 14,
    face: "detail",
    glance: LanesGlance,
    detail: LanesDetail,
    settings: LanesSettings,
    useMotion: started(useLanesMotion),
  },
  {
    id: "file",
    title: "Live file",
    x: 10,
    y: 32,
    w: 8,
    h: 0,
    minW: 6,
    minH: 20,
    face: "detail",
    glance: LiveFileGlance,
    detail: LiveFileDetail,
    settings: LiveFileSettings,
    useMotion: started(useLiveFileMotion),
  },
  {
    id: "report",
    title: "Report",
    x: 18,
    y: 32,
    w: 6,
    h: 34,
    minW: 5,
    minH: 14,
    face: "detail",
    glance: ReportGlance,
    detail: ReportDetail,
    settings: ReportSettings,
    useMotion: started(useReportMotion),
  },
  {
    id: "log",
    title: "Log",
    x: 0,
    y: 66,
    w: 10,
    h: 0,
    minW: 6,
    minH: 14,
    face: "detail",
    glance: LogGlance,
    detail: LogDetail,
    settings: LogSettings,
    useMotion: started(useLogMotion),
  },
  {
    id: "claims",
    title: "Claims",
    x: 18,
    y: 66,
    w: 6,
    h: 0,
    minW: 4,
    minH: 12,
    glance: ClaimsGlance,
    detail: ClaimsDetail,
    useMotion: started(useClaimsMotion),
  },
];
