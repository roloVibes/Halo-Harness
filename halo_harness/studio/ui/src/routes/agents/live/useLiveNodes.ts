// What Live draws: one session's agent tree (the session picked, else this harness's newest with an agent at work, else
// its newest) with a live Orchestra run's lead and lanes under it (runLanes.tsx); Session's Map (`thumb`) this harness's
// sessions and their agents (fleetModel.ts). Recomputed as the frames move and once a second (the elapsed times).
// 3.3.18.0 "The living canvas": Live draws only what is present (now.ts: a finished agent for ten seconds, a failed one
// until dismissed, the parents that hold them); a replay from History (replay.ts) stands in for all of it.
import { useMemo } from "react";
import { recordRefs, useSessionRecord, type RecordRef, type WorkRecord } from "../../../lib/work/record";
import { fleet, useFleet, useNow, type FleetState } from "../../fleet/store";
import { useOrch } from "../../orchestra/store";
import { liveNodes, type LiveNode } from "../../roles/liveModel";
import { useRoles } from "../../roles/store";
import { fleetNodes } from "./fleetModel";
import { pickSession, present, useDismissed } from "./now";
import { useLiveReplay } from "./replay";
import { runNodes } from "./runLanes";

export type LiveNodes = { nodes: LiveNode[]; sid: string; refs: RecordRef[]; now: number; replay: boolean; rec: WorkRecord | null };

export function useLiveNodes(mode: "here" | "thumb"): LiveNodes {
  const run = useOrch((s) => s.data);
  const want = useRoles((s) => s.liveSid);
  const graph = useRoles((s) => s.graph);
  const lineup = useRoles((s) => s.name);
  const harnesses = useFleet((s) => s.harnesses);
  const activity = useFleet((s) => s.activity);
  const doneAt = useFleet((s) => s.doneAt);
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
    if (mode === "thumb") return fleetNodes(fleet.get(), graph?.nodes || [], lineup, now, local || "?");
    if (replay) return replay.nodes;
    const all = [...(rec ? liveNodes(rec, fleet.get(), graph?.nodes || [], lineup, now) : []), ...lanes];
    return present(all, doneAt, now, gone, new Set());
  }, [mode, rec, graph, lineup, activity, doneAt, harnesses, now, lanes, local, gone, replay]);
  const at = replay && mode !== "thumb" ? replay.t * 1000 : now; // 3.4.1.0 R1: a replay's boxes tick at the scrubber's moment
  return { nodes, sid, refs, now: at, replay: !!replay && mode !== "thumb", rec };
}
