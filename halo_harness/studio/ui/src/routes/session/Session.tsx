// Session (Alt+1 and the first tab since 3.1.6.0 R6; 3.1.4.0 R2 "The session dashboard"; 3.1.5.0 R3 "the
// entire right side ... seeing everything working in real time"): this
// session, live. The Fleet panels scoped to this harness (routes/fleet/
// scope.ts; the section sets the scope while it shows, store.ts), no copy of
// any of them, plus two of its own. The left column: Map (session-map: one
// card per session on this box and its agent tree drawn as a tree, who spawned
// whom, what each runs on and costs, the tool running and for how long) over
// Cost (session-cost, Cost.tsx: the spend and its sparkline, the context
// filling, cost per turn, each agent's share). The whole right side: Live
// (session-live, Live.tsx: every agent's text, tool calls and output in one
// column, as they happen). Agent (the inspector, Steer, Pause, Stop, Follow,
// Pin), Activity (the timeline lanes and the full log) and Attention (this
// harness's rows, one key each) wait as strips under Cost, one click away.
// Until this harness has a live session the section is its Start view.
// 3.1.5.0 R3 follow-up: a panel's face draws only while Session shows (a
// visited section stays mounted): nothing of Session runs for the Fleet page.
import { useEffect, type ComponentType } from "react";
import { studio, useStore } from "../../lib/store";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ActivityDetail, ActivityGlance, useActivityMotion } from "../fleet/Activity";
import { AgentDetail, AgentGlance, AgentSettings, useAgentMotion } from "../fleet/Agent";
import { AttentionDetail, AttentionGlance, useAttentionMotion } from "../fleet/Attention";
import { MapDetail, MapGlance, useMapMotion } from "../fleet/Map";
import { CostDetail, CostGlance, useCostMotion } from "./Cost";
import { LiveDetail, LiveGlance, useLiveMotion } from "./Live";
import { WhySettings } from "./Why";
import { startSession } from "./store";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startSession(), []);
    return hook();
  };
}

/** The face, drawn only while the Session section shows. */
function whileShown(Face: ComponentType): ComponentType {
  return function Shown() {
    return useStore(studio, (s) => s.section === "session") ? <Face /> : null;
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({
  id, testid: id, ...HELP[id], ...rest, glance: whileShown(rest.glance), detail: rest.detail && whileShown(rest.detail),
});

// 24 columns, 8 px rows; h 0 fills the visible height, a negative h fills it but leaves that many rows below.
// Left (10 columns, about 40 %): Map (46 rows, the tree fitted to it) over Cost (to the bottom, less the 15
// rows of the three strips under it: Agent, Activity, Attention; a y past the others only orders them, the
// grid packs them up).
// Right (14 columns, about 60 %, the full height): Live. The list order is the "+" menu's and the palette's.
export const sessionPanels: PanelSpec[] = [
  panel("session-map", { title: "Map", x: 0, y: 0, w: 10, h: 46, minW: 7, minH: 20, face: "detail", glance: MapGlance, detail: MapDetail, useMotion: started(useMapMotion) }),
  panel("session-live", { title: "Live", primary: true, x: 10, y: 0, w: 14, h: 0, minW: 6, minH: 30, face: "detail", glance: LiveGlance, detail: LiveDetail, settings: WhySettings, useMotion: started(useLiveMotion) }),
  panel("session-cost", { title: "Cost", x: 0, y: 46, w: 10, h: -15, minW: 4, minH: 14, face: "detail", glance: CostGlance, detail: CostDetail, useMotion: started(useCostMotion) }),
  panel("session-agent", { title: "Agent", x: 0, y: 200, w: 10, h: 0, minW: 5, minH: 32, face: "detail", collapsed: true, glance: AgentGlance, detail: AgentDetail, settings: AgentSettings, useMotion: started(useAgentMotion) }),
  panel("session-activity", { title: "Activity", x: 0, y: 205, w: 10, h: 0, minW: 5, minH: 24, face: "detail", collapsed: true, glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion) }),
  panel("session-attention", { title: "Attention", x: 0, y: 210, w: 10, h: 0, minW: 4, minH: 18, face: "detail", collapsed: true, glance: AttentionGlance, detail: AttentionDetail, useMotion: started(useAttentionMotion) }),
];
