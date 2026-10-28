// Fleet (Alt+4): every connected harness, its sessions and every agent in
// them, live. Before anything is here the section is the Start view
// (Start.tsx); then nine panels on the movable workspace. 3.1.4.0 R1 (the
// owner's live check: "really busy"): five open, in three columns. On the
// left People (fleet-people, who is in the fleet) and Costs (fleet-costs,
// spend and caps) on their compact faces over Attention (fleet-attention,
// every decision that waits on you, one key each); in the middle Map
// (fleet-map) over Activity (fleet-activity, the timeline strip and the
// merged live log, the full width of the map). Down the right edge four
// title strips, one click away, each opening in that column: Health
// (fleet-health, a doctor summary per harness), Capabilities
// (fleet-capabilities, 3.0.6.0 R6: a spec card per harness and "Who
// can..."), Agent (fleet-agent, the selected agent's streams, Steer,
// hand-offs, Record; picking an agent opens it) and Mission (fleet-mission,
// 3.0.6.0 R8: one goal for the whole fleet; M opens it). A layout saved
// before keeps its places (halo.studio.layout.fleet). Two stores: the map's
// (store.ts, fed by sync.ts) and the panels' (pstore.ts, fed by pload.ts);
// the hop keys, the mini stream, Live Roles and the canvas replay work from
// every section. 3.3.2.0 R2: Tree (fleet-tree, FleetTree.tsx, optional: the
// header's "+" adds it) is the tree the expanded rail used to carry, with its
// inline answers and the "While you were away" card. 3.3.4.0 R5: Ollama (fleet-ollama, Ollama.tsx,
// optional: the "+" adds it, the steward's attention row and the palette open it), the Ollama steward's panel.
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
import { treePanel } from "./FleetTree";
import { ollamaPanel } from "./Ollama";
import { startFleet } from "./sync";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startFleet(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "testid">): PanelSpec => ({ id, testid: id, ...HELP[id], ...rest });

// 3.1.4.0 R1: columns 0-5 hold People and Costs (22 rows each: a two-line glance hint fits at 12 px) over
// Attention; 6-17 the Map (44 rows, level with them) over Activity; 18-23 Health, Capabilities, Agent and
// Mission as title strips (`collapsed`), each one click away and opening in that column, where it pushes only
// the strips under it down (Agent, which a picked agent opens, sits above Mission, so it opens in view). The
// list keeps its order: the "+" menu, the palette and "How Fleet works" list the panels in it.
export const fleetPanels: PanelSpec[] = [
  panel("fleet-people", { title: "People", x: 0, y: 0, w: 6, h: 22, minW: 5, minH: 10, face: "glance", glance: PeopleGlance, detail: PeopleDetail, useMotion: started(usePeopleMotion) }),
  panel("fleet-costs", { title: "Costs", x: 0, y: 22, w: 6, h: 22, minW: 5, minH: 10, face: "glance", glance: CostsGlance, detail: CostsDetail, useMotion: started(useCostsMotion) }),
  panel("fleet-health", { title: "Health", x: 18, y: 0, w: 6, h: 20, minW: 5, minH: 10, face: "glance", collapsed: true, glance: HealthGlance, detail: HealthDetail, useMotion: started(useHealthMotion) }),
  panel("fleet-attention", { title: "Attention", x: 0, y: 44, w: 6, h: 0, minW: 4, minH: 16, face: "detail", glance: AttentionGlance, detail: AttentionDetail, useMotion: started(useAttentionMotion) }),
  panel("fleet-map", { title: "Map", primary: true, x: 6, y: 0, w: 12, h: 44, minW: 8, minH: 24, face: "detail", glance: MapGlance, detail: MapDetail, useMotion: started(useMapMotion) }),
  panel("fleet-activity", { title: "Activity", x: 6, y: 44, w: 12, h: 0, minW: 4, minH: 16, face: "detail", glance: ActivityGlance, detail: ActivityDetail, useMotion: started(useActivityMotion) }),
  panel("fleet-mission", { title: "Mission", x: 18, y: 15, w: 6, h: 0, minW: 6, minH: 18, face: "detail", collapsed: true, glance: MissionGlance, detail: MissionDetail, useMotion: started(useMissionMotion) }),
  panel("fleet-capabilities", { title: "Capabilities", x: 18, y: 5, w: 6, h: 22, minW: 5, minH: 12, face: "glance", collapsed: true, glance: CapabilitiesGlance, detail: CapabilitiesDetail, useMotion: started(useCapabilitiesMotion) }),
  panel("fleet-agent", { title: "Agent", x: 18, y: 10, w: 6, h: 0, minW: 5, minH: 32, face: "detail", collapsed: true, glance: AgentGlance, detail: AgentDetail, settings: AgentSettings, useMotion: started(useAgentMotion) }),
  treePanel, // 3.3.2.0 R2: optional, FleetTree.tsx
  ollamaPanel, // 3.3.4.0 R5: optional, Ollama.tsx
];
