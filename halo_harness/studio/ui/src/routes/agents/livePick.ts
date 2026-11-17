// Which session Agents -> 4 · Live draws (3.6.0.2 R3 R34 R5): Session's chosen session (routes/session/store.ts
// `chosenSession`: the pick kept in `sess.chosen` once the scope is cleared off Session), else the newest open one here.
// The picker "{title} · {map}" lists this machine's open sessions (litStore `openList`: T10 last) then every other
// machine's open session the fleet rows show (`openAway`); it is drawn only when there are two or more. A pick here of a
// local session is Session's pick too (R1: kept until he picks another or it ends); a pick of another machine's session
// stays Live's own (Session picks local sessions only, R3) and reads T9, with no drawing and no fetch.
import { useMemo } from "react";
import { createStore, useStore } from "../../lib/store";
import { localId, useFleet } from "../fleet/store";
import type { SessionRow } from "../fleet/types";
import { openAway, openList } from "../crew/map/litStore";
import type { TruthFacts } from "../crew/map/truth";
import { mapName } from "../crew/map/truthWords";
import { factsOf, knownNext, lastRow } from "../session/pick";
import { noneFacts } from "../session/SessionMap";
import { chosenSession, sess, useSession } from "../session/store";

/** Another machine's session picked in Live (its sid), "" when the pick is a local one. */
const away = createStore<{ sid: string }>({ sid: "" });

export type LiveOpt = { sid: string; text: string; away?: boolean };
export type LivePick = { sid: string; f: TruthFacts; row: SessionRow | null; local: boolean; opts: LiveOpt[]; value: string };

/** One option of the picker: "{title} · {map}" ({map} as truth.ts writes {A}: "starter (the default)" for the default). */
export function optText(r: Pick<SessionRow, "session_id" | "title" | "map" | "map_plain">): string {
  const a = typeof r.map === "string" && r.map ? mapName(r.map, !!r.map_plain) : "no map";
  return `${String(r.title || r.session_id.slice(0, 8))} · ${a}`;
}

/** Pick a session in the picker: a local one is Session's pick too; another machine's stays Live's. */
export function pickLive(sid: string, local: boolean): void {
  away.update(() => ({ sid: local ? "" : sid }));
  if (local) sess.update(() => ({ chosen: sid }));
}

export function useLivePick(): LivePick {
  const harnesses = useFleet((s) => s.harnesses);
  const here = useFleet((s) => localId(s));
  const chosen = useSession((s) => s.chosen); // the pick a click here writes: re-read the row with it
  const row = useFleet(chosenSession);
  const pick = useFleet((s) => s.scope.session || "") || chosen;
  const awaySid = useStore(away, (s) => s.sid);
  return useMemo(() => {
    const mine = openList({ harnesses }, here);
    const rowsHere = harnesses.filter((h) => h.id === here || h.local).flatMap((h) => h.sessions || []);
    const others = openAway({ harnesses }, here);
    const rowOf = (sid: string) => harnesses.filter((h) => h.id !== here && !h.local).flatMap((h) => h.sessions || []).find((r) => r.session_id === sid);
    const opts: LiveOpt[] = [
      ...mine.map((s) => ({ sid: s.sid, text: optText(rowsHere.find((r) => r.session_id === s.sid) || { session_id: s.sid, title: s.title }) })),
      ...others.map((o) => ({ sid: o.sid, text: optText(rowOf(o.sid) || { session_id: o.sid, title: o.title }), away: true })),
    ];
    const far = awaySid ? others.find((o) => o.sid === awaySid) : undefined;
    const farRow = far ? rowOf(far.sid) : undefined;
    if (far && farRow) return { sid: far.sid, f: { ...factsOf(farRow), machine: far.machine }, row: farRow, local: false, opts, value: far.sid };
    const ended = !row && pick ? lastRow(pick) : null; // R4: one that ended reads T8 until another is picked
    const sid = row?.session_id || (ended ? pick : "");
    const f = row ? factsOf(row) : ended ? factsOf(ended.row, ended.ended) : noneFacts(knownNext()?.b ?? null);
    return { sid, f, row: row || ended?.row || null, local: true, opts, value: sid };
  }, [harnesses, here, row, pick, awaySid, chosen]);
}
