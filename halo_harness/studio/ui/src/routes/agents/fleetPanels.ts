// Activity (`fleet-activity`, its panel id kept: the timeline strip and the merged live log) is an optional panel of
// Live (roles), closed on load -- the header's "+" and the palette add it. It takes its place in the workspace's grid
// when added.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ActivityDetail, ActivityGlance, useActivityMotion } from "../fleet/Activity";
import { startFleet } from "../fleet/sync";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startFleet(), []);
    return hook();
  };
}

export const activityPanel: PanelSpec = {
  id: "fleet-activity", testid: "fleet-activity", ...HELP["fleet-activity"], title: "Activity", x: 0, y: 0, w: 12, h: 40, minW: 4, minH: 16,
  face: "detail", optional: true, glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion),
};
