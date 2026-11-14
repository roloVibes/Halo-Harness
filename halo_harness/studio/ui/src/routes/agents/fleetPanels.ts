// Activity (`fleet-activity`, its panel id kept: the timeline strip and the merged live log) is an optional panel of
// Live (roles), closed on load -- the view bar and the palette add it. 3.6.0.0 R0a: a tab of the canvas (the timeline
// is wide: it takes the main place while it shows).
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
  id: "fleet-activity", testid: "fleet-activity", ...HELP["fleet-activity"], title: "Activity", role: "tab", fullGrow: 3,
  face: "detail", optional: true, glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion),
};
