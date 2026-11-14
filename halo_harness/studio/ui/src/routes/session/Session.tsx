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
// 3.3.11.0 R1: Prompt (session-prompt, Prompt.tsx), the fourth strip under Cost: type into the session as in
// the terminal (Alt+Enter, the palette, `?prompt=1`), what it sends with its receipt.
import { useEffect, type ComponentType } from "react";
import { studio, useStore } from "../../lib/store";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ActivityDetail, ActivityGlance, useActivityMotion } from "../fleet/Activity";
import { AgentDetail, AgentGlance, AgentSettings, useAgentMotion } from "../fleet/Agent";
import { AttentionDetail, AttentionGlance, useAttentionMotion } from "../fleet/Attention";
import { MapDetail, MapGlance, useMapMotion } from "./SessionMap";
import { CostDetail, CostGlance, useCostMotion } from "./Cost";
import { ConversationsDetail, ConversationsGlance, useConversationsMotion } from "./Conversations";
import { LiveDetail, LiveGlance, useLiveMotion } from "./Live";
import { PromptDetail, PromptGlance, usePromptMotion } from "./Prompt";
import { registerPromptPanel, startPrompt } from "./promptStore";
import { WhySettings } from "./Why";
import { startSession } from "./store";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => (startSession(), startPrompt()), []);
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

// 3.6.0.0 R0a, the stage: Live is the main thing; Activity (the timeline and the full log, wide) is its tab; Map is a
// left drawer (the tree), Cost, Agent, Attention and Prompt right drawers, each as wide as its content. Every other
// panel is a button in the view bar, closed on load. The list order is the bar's and the palette's.
export const sessionPanels: PanelSpec[] = [
  panel("session-map", { title: "Map", side: "left", contentW: 360, face: "detail", glance: MapGlance, detail: MapDetail, useMotion: started(useMapMotion) }),
  panel("session-live", { title: "Live", primary: true, face: "detail", glance: LiveGlance, detail: LiveDetail, settings: WhySettings, useMotion: started(useLiveMotion) }),
  panel("session-cost", { title: "Cost", contentW: 360, face: "detail", glance: CostGlance, detail: CostDetail, useMotion: started(useCostMotion) }),
  panel("session-agent", { title: "Agent", contentW: 400, face: "detail", collapsed: true, glance: AgentGlance, detail: AgentDetail, settings: AgentSettings, useMotion: started(useAgentMotion) }),
  panel("session-activity", { title: "Activity", role: "tab", face: "detail", collapsed: true, glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion) }),
  panel("session-attention", { title: "Attention", contentW: 360, face: "detail", collapsed: true, glance: AttentionGlance, detail: AttentionDetail, useMotion: started(useAttentionMotion) }),
  panel("session-prompt", { title: "Prompt", contentW: 420, face: "detail", collapsed: true, glance: PromptGlance, detail: PromptDetail, useMotion: started(usePromptMotion) }),
  // 3.3.16.2: agents talking, one thread per pair (Conversations.tsx); optional: the "+" menu adds it
  panel("session-conversations", { title: "Conversations", contentW: 440, face: "detail", optional: true, glance: ConversationsGlance, detail: ConversationsDetail, useMotion: started(useConversationsMotion) }),
];
registerPromptPanel(sessionPanels.find((p) => p.id === "session-prompt"));
