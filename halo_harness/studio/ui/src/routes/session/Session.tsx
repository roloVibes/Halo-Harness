// Session (Alt+8, 3.1.4.0 R2 "The session dashboard"): this session, live.
// The Fleet panels scoped to this harness (routes/fleet/scope.ts; the
// section sets the scope while it shows, store.ts), no copy of any of them:
// Map (session-map: one card per session on this box and its agent tree, the
// working node lit), Agent (session-agent: the inspector, Steer, Pause /
// Resume, Stop, Follow, Pin), Activity (session-activity: the timeline lanes
// and the log of the chosen session, or of every session here), Attention
// (session-attention: this harness's rows, one key each) and one panel of its
// own, Cost (session-cost, Cost.tsx: the chosen session's spend, tokens,
// turns, elapsed, model). Five panels, nothing fleet-wide. Until this harness
// has a live session the section is its Start view (Start.tsx).
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ActivityDetail, ActivityGlance, useActivityMotion } from "../fleet/Activity";
import { AgentDetail, AgentGlance, AgentSettings, useAgentMotion } from "../fleet/Agent";
import { AttentionDetail, AttentionGlance, useAttentionMotion } from "../fleet/Attention";
import { MapDetail, MapGlance, useMapMotion } from "../fleet/Map";
import { CostDetail, CostGlance, useCostMotion } from "./Cost";
import { startSession } from "./store";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startSession(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest });

// 24 columns, 8 px rows; h 0 fills the visible height. The map and the log on the left, the agent in the
// middle, the small Cost panel over Attention on the right.
export const sessionPanels: PanelSpec[] = [
  panel("session-map", { title: "Map", x: 0, y: 0, w: 10, h: 44, minW: 7, minH: 20, face: "detail", glance: MapGlance, detail: MapDetail, useMotion: started(useMapMotion) }),
  panel("session-agent", { title: "Agent", x: 10, y: 0, w: 8, h: 0, minW: 5, minH: 32, face: "detail", glance: AgentGlance, detail: AgentDetail, settings: AgentSettings, useMotion: started(useAgentMotion) }),
  panel("session-cost", { title: "Cost", x: 18, y: 0, w: 6, h: 22, minW: 4, minH: 12, face: "detail", glance: CostGlance, detail: CostDetail, useMotion: started(useCostMotion) }),
  panel("session-attention", { title: "Attention", x: 18, y: 22, w: 6, h: 0, minW: 4, minH: 14, face: "detail", glance: AttentionGlance, detail: AttentionDetail, useMotion: started(useAttentionMotion) }),
  panel("session-activity", { title: "Activity", x: 0, y: 44, w: 10, h: 0, minW: 5, minH: 16, face: "detail", glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion) }),
];
