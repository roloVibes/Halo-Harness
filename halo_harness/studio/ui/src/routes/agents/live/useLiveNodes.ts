// What Live draws (3.3.16.0 R2 "the Fleet fold"): on **this halo** one session's agent tree (the session picked, else
// this harness's newest with an agent at work, else its newest) with a live Orchestra run's lead and lanes under it
// (runLanes.tsx); on **fleet** every machine, its sessions and their agents, and the open mission's parts
// (fleetModel.ts); Session's Map (`thumb`) this harness's sessions and their agents, no machine node. Recomputed as the
// frames move and once a second (the elapsed times). 3.3.18.0 "The living canvas": Live draws only what is present
// (now.ts: a finished agent for ten seconds, a failed one until dismissed, the parents that hold them), the open
// mission only while it runs or is being planned; a replay from History (replay.ts) stands in for all of it.
import { useMemo } from "react";
import { recordRefs, useSessionRecord, type RecordRef, type WorkRecord } from "../../../lib/work/record";
import { fleet, useFleet, useNow, type FleetState } from "../../fleet/store";
import { FINAL, LIVE as MISSION_LIVE, useMissions } from "../../fleet/mstore";
import { useOrch } from "../../orchestra/store";
import { liveNodes, type LiveNode } from "../../roles/liveModel";
import { useRoles } from "../../roles/store";
import { fleetNodes } from "./fleetModel";
import { pickSession, present, useDismissed } from "./now";
import { useLiveReplay } from "./replay";
import { runNodes } from "./runLanes";

export type LiveNodes = { nodes: LiveNode[]; sid: string; refs: RecordRef[]; now: number; replay: boolean; rec: WorkRecord | null };

export function useLiveNodes(mode: "here" | "fleet" | "thumb"): LiveNodes {
  const run = useOrch((s) => s.data);
  const want = useRoles((s) => s.liveSid);
  const graph = useRoles((s) => s.graph);
  const lineup = useRoles((s) => s.name);
  const harnesses = useFleet((s) => s.harnesses);
  const activity = useFleet((s) => s.activity);
  const doneAt = useFleet((s) => s.doneAt);
  const mission = useMissions((s) => s.view);
  const list = useMissions((s) => s.list);
  const gone = useDismissed();
  const replay = useLiveReplay();
  const now = useNow(true, 1000);
  const local = harnesses.find((h) => h.local)?.id || "";
  const refs = useMemo(() => {
    const all = recordRefs({ harnesses } as FleetState);
    return mode === "here" && local ? all.filter((r) => r.local || r.id === want) : all;
  }, [harnesses, mode, local, want]);
  const sid = mode === "thumb" ? (want && refs.some((r) => r.id === want) ? want : refs[0]?.id || "") : pickSession(refs, want);
  const rec = useSessionRecord(mode === "here" ? sid : "");
  const lanes = useMemo(() => (mode === "here" ? runNodes(run) : []), [run, mode]);
  const nodes = useMemo(() => {
    if (mode === "thumb") return fleetNodes(fleet.get(), graph?.nodes || [], lineup, now, null, local || "?");
    if (replay) return replay.nodes;
    const open = mode === "fleet" && mission && !FINAL.includes(mission.mission.state) ? mission : null; // a finished mission is History's
    const all = mode === "fleet" ? fleetNodes(fleet.get(), graph?.nodes || [], lineup, now, open)
      : [...(rec ? liveNodes(rec, fleet.get(), graph?.nodes || [], lineup, now) : []), ...lanes];
    const busy = new Set((list || []).filter((m) => MISSION_LIVE.includes(m.state)).map((m) => m.id)); // a running mission's sessions stay
    const keep = new Set(harnesses.flatMap((h) => (h.sessions || []).filter((s) => s.mission && busy.has(String(s.mission))).map((s) => s.session_id)));
    return present(all, doneAt, now, gone, keep);
  }, [mode, rec, graph, lineup, activity, doneAt, harnesses, mission, list, now, lanes, local, gone, replay]);
  return { nodes, sid, refs, now, replay: !!replay && mode !== "thumb", rec };
}
