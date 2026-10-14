// Flow: the workflow console (Alt+5). A brief goes through the roles, the
// marketing org, a ComfyUI render you confirm, then the posts and their
// metrics, all in one design project. Before a run is open the section is
// one Start view (Start.tsx); then eight panels on the movable workspace --
// Intake, Workflow, Renders, Step, Posts, Metrics, Log, Report -- each
// opening on its full face (the Glance face is the summary a strip keeps),
// plus the Media group (ComfyUI) as collapsed strips along the bottom. One
// store (store.ts) fed by GET flow/runs/<id> and the feed's flow_* frames.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { mediaPanels } from "../media/MediaPanels";
import { GraphDetail, GraphGlance, useGraphMotion } from "./Graph";
import { IntakeDetail, IntakeGlance, IntakeSettings, useIntakeMotion } from "./Intake";
import { LogDetail, LogGlance, LogSettings, useLogMotion } from "./Log";
import { MetricsDetail, MetricsGlance, useMetricsMotion } from "./Metrics";
import { PostsDetail, PostsGlance, usePostsMotion } from "./Posts";
import { RendersDetail, RendersGlance, useRendersMotion } from "./Renders";
import { ReportDetail, ReportGlance, ReportSettings, useReportMotion } from "./Report";
import { StepDetail, StepGlance, StepSettings, useStepMotion } from "./Step";
import { startFlow } from "./sync";

/** A panel's motion hook that also starts the Flow store (once). */
function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startFlow(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "face" | "testid">): PanelSpec => ({ id, face: "detail", testid: id, ...HELP[id], ...rest });

export const flowPanels: PanelSpec[] = [
  panel("flow-intake", { title: "Intake", x: 0, y: 0, w: 7, h: 68, minW: 6, minH: 60, glance: IntakeGlance, detail: IntakeDetail, settings: IntakeSettings, useMotion: started(useIntakeMotion) }),
  panel("flow-graph", { title: "Workflow", x: 7, y: 0, w: 11, h: 34, minW: 8, minH: 16, glance: GraphGlance, detail: GraphDetail, useMotion: started(useGraphMotion) }),
  panel("flow-renders", { title: "Renders", x: 18, y: 0, w: 6, h: 68, minW: 4, minH: 20, glance: RendersGlance, detail: RendersDetail, useMotion: started(useRendersMotion) }),
  panel("flow-step", { title: "Step", x: 7, y: 34, w: 6, h: 34, minW: 5, minH: 14, glance: StepGlance, detail: StepDetail, settings: StepSettings, useMotion: started(useStepMotion) }),
  panel("flow-posts", { title: "Posts", x: 13, y: 34, w: 5, h: 34, minW: 4, minH: 12, glance: PostsGlance, detail: PostsDetail, useMotion: started(usePostsMotion) }),
  panel("flow-log", { title: "Log", x: 0, y: 68, w: 13, h: 20, minW: 6, minH: 12, glance: LogGlance, detail: LogDetail, settings: LogSettings, useMotion: started(useLogMotion) }),
  panel("flow-metrics", { title: "Metrics", x: 13, y: 68, w: 5, h: 20, minW: 4, minH: 12, glance: MetricsGlance, detail: MetricsDetail, useMotion: started(useMetricsMotion) }),
  panel("flow-report", { title: "Report", x: 18, y: 68, w: 6, h: 20, minW: 4, minH: 12, glance: ReportGlance, detail: ReportDetail, settings: ReportSettings, useMotion: started(useReportMotion) }),
  ...mediaPanels(88, "collapsed"),
];
