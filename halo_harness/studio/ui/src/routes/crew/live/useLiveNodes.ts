// The live nodes of this harness's session at work (3.6.0.0 R5, the old Live's `useLiveNodes("here")` without the tree:
// Session's glance reads them for its one sentence): the newest session with an agent at work, else the newest; what is
// present only (now.ts: a finished agent for ten seconds, a failed one until dismissed); a replay from History stands in
// for all of it. Recomputed as the frames move and once a second (the elapsed times).
import { useMemo } from "react";
import { recordRefs, useSessionRecord, type RecordRef, type WorkRecord } from "../../../lib/work/record";
import { fleet, useFleet, useNow, type FleetState } from "../../fleet/store";
import { liveNodes, type LiveNode } from "./liveModel";
import { pickSession, present, useDismissed } from "./now";
import { useLiveReplay } from "./replay";

export type LiveNodes = { nodes: LiveNode[]; sid: string; refs: RecordRef[]; now: number; replay: boolean; rec: WorkRecord | null };

export function useLiveNodes(): LiveNodes {
  const harnesses = useFleet((s) => s.harnesses);
  const activity = useFleet((s) => s.activity);
  const doneAt = useFleet((s) => s.doneAt);
  const gone = useDismissed();
  const replay = useLiveReplay();
  const now = useNow(true, 1000);
  const local = harnesses.find((h) => h.local)?.id || "";
  const refs = useMemo(() => {
    const all = recordRefs({ harnesses } as FleetState);
    return local ? all.filter((r) => r.local) : all;
  }, [harnesses, local]);
  const sid = pickSession(refs, "");
  const rec = useSessionRecord(sid);
  const nodes = useMemo(() => {
    if (replay) return replay.nodes;
    return present(rec ? liveNodes(rec, fleet.get(), now) : [], doneAt, now, gone, new Set());
  }, [rec, activity, doneAt, harnesses, now, local, gone, replay]);
  return { nodes, sid, refs, now: replay ? replay.t * 1000 : now, replay: !!replay, rec };
}
