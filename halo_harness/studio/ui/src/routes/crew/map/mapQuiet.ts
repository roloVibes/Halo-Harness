// Agents -> 3 · Map's one quiet line (3.6.0.2 R55, R24): the Map is the plan, so a running session is not drawn on it;
// one line in the reserved row says who runs on this map or from it -- L1 a session runs on this map, L2 sessions run on
// other maps while new sessions run on this one (the API's `next`, F4), L3 a session runs a workflow that is a box of
// this map from another map -- and that workflow's box is marked "running now in {session}". The words are truth.ts's.
// The facts are the session rows Studio already has (F2 the row's `map`, a child row tagged `crew.workflow`, P2a).
import { createContext, useContext, useMemo } from "react";
import { localId, useFleet, type FleetState } from "../../fleet/store";
import { openList } from "./litStore";
import { useMap } from "./mapStore";
import type { MapFile } from "./mapTypes";
import { mapLine, nextMap, type Line, type MapLineFacts } from "./truth";
import { onMap } from "./truthWords";

const LIVE = ["queued", "running", "waiting", "paused"];

/** An open session of this machine that runs on a map (T10, no message yet, and a session with no map run on none). */
export type QuietOn = { sid: string; title: string; a: string; plain: boolean; flow: string };
export type Mark = { sid: string; title: string };
export type Quiet = { facts: MapLineFacts | null; sid: string; marks: Record<string, Mark> };

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

/** workflow -> the id of the box that runs it on `m`. */
export function flowBoxes(m: MapFile | null): Record<string, string> {
  const out: Record<string, string> = {};
  for (const b of m?.boxes || []) if (b.workflow && !out[b.workflow]) out[b.workflow] = b.id;
  return out;
}

/** Which line (R55): L3, else L1, else L2 (new sessions run on this map: `next`, none set = Auto), else none; the marks on
 *  the boxes of running workflows. `scope`: the open map's (3.6.0.5: his old file named starter is not Auto, onMap). */
export function quietOf(name: string, boxes: Record<string, string>, on: QuietOn[], next: string | null, scope = ""): Quiet {
  const marks: Record<string, Mark> = {};
  for (const s of on) if (s.flow && boxes[s.flow] && !marks[boxes[s.flow]]) marks[boxes[s.flow]] = { sid: s.sid, title: s.title };
  const l3 = on.find((s) => s.flow && boxes[s.flow] && !onMap(s.a, name, scope));
  if (l3) return { facts: { kind: "L3", session: l3.title, workflow: l3.flow, a: l3.a, plain: l3.plain }, sid: l3.sid, marks };
  const l1 = on.find((s) => onMap(s.a, name, scope));
  if (l1) return { facts: { kind: "L1", session: l1.title }, sid: l1.sid, marks };
  const away = onMap(nextMap(next), name, scope) ? on.filter((s) => !onMap(s.a, name, scope)) : [];
  if (away.length) return { facts: { kind: "L2", on: away.map((s) => ({ session: s.title, a: s.a, plain: s.plain })) }, sid: away[0].sid, marks };
  return { facts: null, sid: "", marks };
}

/** The longest lines the row can be asked to hold with the names it has (its height is reserved for them, R33). */
export function quietRoom(on: QuietOn[], flows: string[], mapNames: string[]): Line[] {
  const longest = (xs: string[]) => xs.reduce((a, b) => (b.length > a.length ? b : a), "");
  const t = new Date(2026, 0, 1, 12, 59).getTime() / 1000; // the widest clock
  const flow = longest(flows), map = longest(mapNames);
  const out: Line[] = [];
  for (const s of on) {
    out.push(...mapLine({ kind: "L1", session: s.title }), ...mapLine({ kind: "L2", on: [{ session: s.title, a: s.a, plain: s.plain }] }),
             ...mapLine({ kind: "L4", map, session: s.title, t }));
    if (flow) out.push(...mapLine({ kind: "L3", session: s.title, workflow: flow, a: s.a, plain: s.plain }));
  }
  if (on.length > 1) out.push(...mapLine({ kind: "L2", on: on.map((s) => ({ session: s.title, a: s.a, plain: s.plain })) }));
  return out;
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
