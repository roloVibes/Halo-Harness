// What lights the Map now (3.6.0.2 R55: the Map is the plan, no run overlay; 3.6.0.3 B Z8: it never draws the past):
// nothing. `useLit` is always off and only carries this machine's running sessions
// (`all`) and other machines' (`away`) for the Map's one quiet line (NoticeRow.tsx). A running session is drawn in
// Agents -> 4 · Live (agents/liveLit.tsx gives Live's session in this same shape through LitCtx).
import { createContext, useContext, useEffect } from "react";
import type { WorkRecord } from "../../../lib/work/record";
import type { Change } from "../types";
import { startLit, useAway, useRunning, type AwaySession, type LitSession } from "./litStore";
import type { Overlay } from "./overlay";

export type Lit = {
  mode: "off" | "live"; session: LitSession | null; all: LitSession[]; other: boolean; nomap: boolean; ov: Overlay | null;
  /** R4b: other machines' running sessions */
  away: AwaySession[];
  rec: WorkRecord | null; card: Change[]; map: string; now: number;
};

const NONE: Change[] = [];
/** The Map tab's Lit: always off (Z8), with the running sessions its quiet line names. */
export function useLit(): Lit {
  useEffect(() => startLit(), []);
  const all = useRunning();
  const away = useAway();
  return { ...OFF, all, away };
}

export const OFF: Lit = { mode: "off", session: null, all: [], away: [], other: false, nomap: false, ov: null, rec: null, card: NONE, map: "", now: 0 };
/** MapMain computes it once (useLit) and every part of the tab reads it here. */
export const LitCtx = createContext<Lit>(OFF);
export const useLitNow = (): Lit => useContext(LitCtx);
