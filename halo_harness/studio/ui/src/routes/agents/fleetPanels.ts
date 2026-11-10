// The two Fleet panels that moved into Agents' workspaces (3.3.16.0 R2 "the Fleet fold"), each keeping its panel id:
// Mission (`fleet-mission`) is an optional panel of Runs (orchestra), beside the Orchestra run -- a mission row of
// Runs' list, an attention row's `o` and `?mode=fleet&mission=<id>` open it; Activity (`fleet-activity`: the timeline
// strip and the merged live log) is an optional panel of Live (roles), closed on load -- the header's "+" and the
// palette add it. Each takes its place in the workspace's grid when added.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ActivityDetail, ActivityGlance, useActivityMotion } from "../fleet/Activity";
import { MissionDetail, MissionGlance, useMissionMotion } from "../fleet/Mission";
import { startFleet } from "../fleet/sync";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startFleet(), []);
    return hook();
  };
}

export const missionPanel: PanelSpec = {
  id: "fleet-mission", testid: "fleet-mission", ...HELP["fleet-mission"], title: "Mission", x: 0, y: 0, w: 12, h: 60, minW: 6, minH: 18,
  face: "detail", optional: true, glance: MissionGlance, detail: MissionDetail, useMotion: started(useMissionMotion),
};

export const activityPanel: PanelSpec = {
  id: "fleet-activity", testid: "fleet-activity", ...HELP["fleet-activity"], title: "Activity", x: 0, y: 0, w: 12, h: 40, minW: 4, minH: 16,
  face: "detail", optional: true, glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion),
};
