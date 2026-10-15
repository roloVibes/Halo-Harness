// Fleet (Alt+6): every connected harness, its sessions and every agent in
// them, live. Before anything is here the section is the Start view
// (Start.tsx); then eight panels on the movable workspace. Along the top,
// on their compact faces: People (fleet-people, who is in the fleet), Costs
// (fleet-costs, spend and caps) and Health (fleet-health, a doctor summary
// per harness). Under them: Attention (fleet-attention, every decision that
// waits on you, one key each), Map (fleet-map), Activity (fleet-activity,
// the timeline strip and the merged live log) and Agent (fleet-agent, the
// selected agent's streams, Steer, hand-offs, Record) and, beside the map
// above Agent, Capabilities (fleet-capabilities, 3.0.6.0 R6: a spec card per
// harness and the "Who can..." search). 3.0.6.0 R8: Mission (fleet-mission,
// one goal for the whole fleet: plan, approve, run, report) sits under the
// map, where Activity was, so the plan it draws on the map stays in view
// right above its table; Activity moves under Attention. Two stores: the map's
// (store.ts, fed by sync.ts) and the panels' (pstore.ts, fed by pload.ts);
// the rail's Fleet tree, the hop keys, the mini stream, Live Roles and the
// canvas replay work from every section.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { ActivityDetail, ActivityGlance, useActivityMotion } from "./Activity";
import { AgentDetail, AgentGlance, AgentSettings, useAgentMotion } from "./Agent";
import { CapabilitiesDetail, CapabilitiesGlance, useCapabilitiesMotion } from "./Capabilities";
import { AttentionDetail, AttentionGlance, useAttentionMotion } from "./Attention";
import { CostsDetail, CostsGlance, useCostsMotion } from "./Costs";
import { HealthDetail, HealthGlance, useHealthMotion } from "./Health";
import { MapDetail, MapGlance, useMapMotion } from "./Map";
import { MissionDetail, MissionGlance, useMissionMotion } from "./Mission";
import { PeopleDetail, PeopleGlance, usePeopleMotion } from "./People";
import { startFleet } from "./sync";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startFleet(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest });

export const fleetPanels: PanelSpec[] = [
  panel("fleet-people", { title: "People", x: 0, y: 0, w: 8, h: 14, minW: 5, minH: 10, face: "glance", glance: PeopleGlance, detail: PeopleDetail, useMotion: started(usePeopleMotion) }),
  panel("fleet-costs", { title: "Costs", x: 8, y: 0, w: 8, h: 14, minW: 5, minH: 10, face: "glance", glance: CostsGlance, detail: CostsDetail, useMotion: started(useCostsMotion) }),
  panel("fleet-health", { title: "Health", x: 16, y: 0, w: 8, h: 14, minW: 5, minH: 10, face: "glance", glance: HealthGlance, detail: HealthDetail, useMotion: started(useHealthMotion) }),
  panel("fleet-attention", { title: "Attention", x: 0, y: 14, w: 5, h: 40, minW: 4, minH: 16, face: "detail", glance: AttentionGlance, detail: AttentionDetail, useMotion: started(useAttentionMotion) }),
  panel("fleet-map", { title: "Map", x: 5, y: 14, w: 11, h: 40, minW: 8, minH: 24, face: "detail", glance: MapGlance, detail: MapDetail, useMotion: started(useMapMotion) }),
  panel("fleet-activity", { title: "Activity", x: 0, y: 54, w: 5, h: 0, minW: 4, minH: 16, face: "detail", glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion) }),
  // 3.0.6.0 R8: Mission under the map (the plan's table right under its drawing), Activity under Attention
  panel("fleet-mission", { title: "Mission", x: 5, y: 54, w: 11, h: 0, minW: 6, minH: 18, face: "detail", glance: MissionGlance, detail: MissionDetail, useMotion: started(useMissionMotion) }),
  // 3.0.6.0 R6: Capabilities at 16,14 on its compact face (the Who box), the agent panel stacked under it
  panel("fleet-capabilities", { title: "Capabilities", x: 16, y: 14, w: 8, h: 18, minW: 5, minH: 12, face: "glance", glance: CapabilitiesGlance, detail: CapabilitiesDetail, useMotion: started(useCapabilitiesMotion) }),
  panel("fleet-agent", { title: "Agent", x: 16, y: 32, w: 8, h: 0, minW: 5, minH: 32, face: "detail", glance: AgentGlance, detail: AgentDetail, settings: AgentSettings, useMotion: started(useAgentMotion) }),
];
