// 4 · Live's session for its Feed (3.6.0.2 R57: the Feed is keyed to Live's session): the session Live shows (livePick.ts)
// in the Lit shape the Feed, its head (BoxHead) and its pages read (crew/map/useLit.ts), given to the whole workspace
// through LitCtx. A local session gives its words whatever its T-state; its overlay (which box holds which agents) comes
// from the drawing's own read (LitMini useLit, cached by version: nothing is read twice) only while Live draws it, so a
// session Live does not draw (T8, T10) reads no map (R28). Another machine's session (T9), or none: no Feed. P8 (the
// coordinator's ruling): a session with NO map (T4) is drawn as Session's Live drawer draws it -- the box main alone,
// through the same drawing (LiveDraw.tsx, useLit's map of no file: nothing is read) -- under its T4 line, so an ask's door
// from Agents lands on main's box with the ask's card: a run's drawing is never an empty page while a session runs.
import { useMemo, type ReactNode } from "react";
import { useSessionRecord } from "../../lib/work/record";
import { useNow } from "../fleet/store";
import { useLit } from "../crew/map/LitMini";
import { toLit, type LitSession } from "../crew/map/litStore";
import { truthState } from "../crew/map/truth";
import { LitCtx, OFF, type Lit } from "../crew/map/useLit";
import { useLivePick, type LivePick } from "./livePick";
import { useShown } from "../crew/map/runParts";

const DRAWN = new Set(["T1", "T2", "T3", "T4", "T11", "T12"]); // a local open session, with a map or with none (main alone)
const NOBODY: LitSession = { sid: "", title: "", map: null, started: 0, live: 0 };

/** The session Live draws (a local open session with a map), or null. */
export const liveRun = (p: LivePick): LitSession | null => (p.local && p.row && DRAWN.has(truthState(p.f)) ? toLit(p.row) : null);

export function LiveLit({ children }: { children: ReactNode }) {
  const p = useLivePick();
  const s = p.local && p.row ? toLit(p.row) : null;
  const drawn = liveRun(p);
  const on = useShown("live"); // P4 batch 13: no clock of a hidden Live runs
  const M = useLit(drawn || NOBODY, undefined, on);
  const rec = useSessionRecord(s?.sid || "");
  const now = useNow(!!s && on, 1000) / 1000;
  const sid = s?.sid || "", map = s?.map || "";
  const ov = drawn ? M.ov : null;
  const value = useMemo<Lit>(() => (!s ? OFF : { ...OFF, mode: "live", session: s, all: [s], map, ov, rec, now }),
    [sid, map, ov, rec, now]); // eslint-disable-line react-hooks/exhaustive-deps
  return <LitCtx.Provider value={value}>{children}</LitCtx.Provider>;
}
