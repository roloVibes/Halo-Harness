// Agents -> 3 · Map's one quiet line (3.6.0.2 R55, R24): the Map is the plan, so a running session is not drawn on it;
// one line in the reserved row says who runs on this map or from it (the rule, pure: quietOf.ts) -- and a running
// workflow's box is marked "running now in {session}". The words are truth.ts's.
// The facts are the session rows Studio already has (F2 the row's `map`, a child row tagged `crew.workflow`, P2a).
import { createContext, useContext, useMemo } from "react";
import { localId, useFleet, type FleetState } from "../../fleet/store";
import { openList } from "./litStore";
import { useMap } from "./mapStore";
import { flowBoxes, quietOf, type Mark, type Quiet, type QuietOn } from "./quietOf";

export { flowBoxes, quietOf, quietRoom, type Mark, type Quiet, type QuietOn } from "./quietOf";

const LIVE = ["queued", "running", "waiting", "paused"];

export function openOn(st: Pick<FleetState, "harnesses">, here: string): QuietOn[] {
  const rows = st.harnesses.filter((h) => h.id === here || h.local).flatMap((h) => h.sessions || []);
  return openList(st, here).flatMap((s) => {
    const row = rows.find((r) => r.session_id === s.sid);
    const t10 = !!row && String(row.parent || "").startsWith("studio:") && !row.asked && !Number(row.turns);
    if (!row || !s.map || t10) return [];
    const flow = (row.agents || []).find((a) => LIVE.includes(String(a.state || "")) && a.crew?.workflow)?.crew?.workflow || "";
    return [{ sid: s.sid, title: s.title, a: s.map, plain: !!s.plain, flow: String(flow) }];
  });
}

export function useQuiet(): Quiet & { on: QuietOn[] } {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  const name = useMap((s) => s.name);
  const file = useMap((s) => s.detail?.map || null);
  const next = useMap((s) => s.next);
  const scope = useMap((s) => s.detail?.scope || "");
  return useMemo(() => {
    const on = openOn({ harnesses }, here);
    return { ...quietOf(name, flowBoxes(file), on, next, scope), on };
  }, [harnesses, here, name, file, next, scope]);
}

/** MapMain computes it once; a box reads its mark here. */
export const QuietCtx = createContext<Quiet>({ facts: null, sid: "", marks: {} });
export const useMark = (box: string): Mark | undefined => useContext(QuietCtx).marks[box];
