// What Live draws (3.3.16.0 R2 "the Fleet fold"): on **this halo** one session's agent tree (the session picked, else
// this harness's newest) with a live Orchestra run's lead and lanes under it (runLanes.tsx); on **fleet** every machine,
// its sessions and their agents, and the open mission's parts (fleetModel.ts); Session's Map (`thumb`) this harness's
// sessions and their agents, no machine node. Recomputed as the frames move and once a second (the elapsed times).
import { useMemo } from "react";
import { recordRefs, useSessionRecord, type RecordRef } from "../../../lib/work/record";
import { fleet, useFleet, useNow, type FleetState } from "../../fleet/store";
import { useMissions } from "../../fleet/mstore";
import { useOrch } from "../../orchestra/store";
import { liveNodes, type LiveNode } from "../../roles/liveModel";
import { useRoles } from "../../roles/store";
import { fleetNodes } from "./fleetModel";
import { runNodes } from "./runLanes";

export type LiveNodes = { nodes: LiveNode[]; sid: string; refs: RecordRef[]; now: number };

export function useLiveNodes(mode: "here" | "fleet" | "thumb"): LiveNodes {
  const run = useOrch((s) => s.data);
  const want = useRoles((s) => s.liveSid);
  const graph = useRoles((s) => s.graph);
  const lineup = useRoles((s) => s.name);
  const harnesses = useFleet((s) => s.harnesses);
  const activity = useFleet((s) => s.activity);
  const doneAt = useFleet((s) => s.doneAt);
  const mission = useMissions((s) => s.view);
  const now = useNow(true, 1000);
  const local = harnesses.find((h) => h.local)?.id || "";
  const refs = useMemo(() => {
    const all = recordRefs({ harnesses } as FleetState);
    return mode === "here" && local ? all.filter((r) => r.local || r.id === want) : all;
  }, [harnesses, mode, local, want]);
  const sid = want && refs.some((r) => r.id === want) ? want : refs[0]?.id || "";
  const rec = useSessionRecord(mode === "here" ? sid : "");
  const lanes = useMemo(() => (mode === "here" ? runNodes(run) : []), [run, mode]);
  const nodes = useMemo(() => {
    if (mode !== "here") return fleetNodes(fleet.get(), graph?.nodes || [], lineup, now, mode === "fleet" ? mission : null, mode === "thumb" ? local || "?" : "");
    return [...(rec ? liveNodes(rec, fleet.get(), graph?.nodes || [], lineup, now) : []), ...lanes];
  }, [mode, rec, graph, lineup, activity, doneAt, harnesses, mission, now, lanes, local]);
  return { nodes, sid, refs, now };
}
