// Fleet (Alt+6): every connected harness, its sessions and every agent in
// them, live. Before anything is here the section is the Start view
// (Start.tsx); then two panels on the movable workspace: Map (fleet-map) and
// Agent (fleet-agent, the inspector for the selected agent with its three
// streams and the Steer box). One store (store.ts) fed by GET fleet and the
// feed (sync.ts); the rail's Fleet tree (FleetRail.tsx), the hop keys
// (hop.ts), the mini stream (Pip.tsx) and Live Roles (frames.ts) work from
// every section.
import { useEffect } from "react";
import type { MotionState } from "../../lib/motion";
import type { PanelSpec } from "../../lib/workspace/types";
import { HELP } from "../help";
import { AgentDetail, AgentGlance, AgentSettings, useAgentMotion } from "./Agent";
import { MapDetail, MapGlance, useMapMotion } from "./Map";
import { startFleet } from "./sync";

function started(hook: () => MotionState): () => MotionState {
  return () => {
    useEffect(() => startFleet(), []);
    return hook();
  };
}

const panel = (id: string, rest: Omit<PanelSpec, "id" | "face" | "testid">): PanelSpec => ({ id, face: "detail", testid: id, ...HELP[id], ...rest });

export const fleetPanels: PanelSpec[] = [
  panel("fleet-map", { title: "Map", x: 0, y: 0, w: 14, h: 0, minW: 8, minH: 24, glance: MapGlance, detail: MapDetail, useMotion: started(useMapMotion) }),
  panel("fleet-agent", { title: "Agent", x: 14, y: 0, w: 10, h: 0, minW: 6, minH: 32, glance: AgentGlance, detail: AgentDetail, settings: AgentSettings, useMotion: started(useAgentMotion) }),
];
