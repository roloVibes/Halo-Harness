// The motion vocabulary: one small set of named state motions, so motion
// means the same thing on every element. Put `data-motion="<state>"` on any
// element (or spread `useStateMotion(state)`); the CSS in styles/motion.css
// draws it, and under prefers-reduced-motion it becomes a static colour cue.
//
//   idle     slow breathing glow on the border (4 s)       -- present, nothing running
//   working  a thin light flowing along the top edge         -- something is running
//   waiting  soft amber pulse (1.2 s)                        -- it needs you
//   done     one brief green sweep, then still               -- it just finished
//   error    one red flash, then a steady red edge           -- it failed
//   live     a small dot that ticks once per event           -- a feed is connected
//   none     no motion
import { useEffect, useRef, useState } from "react";

export type MotionState = "idle" | "working" | "waiting" | "done" | "error" | "live" | "none";
export const MOTION_STATES: MotionState[] = ["idle", "working", "waiting", "done", "error", "live", "none"];

export type MotionAttrs = { "data-motion": MotionState; "data-tick"?: "a" | "b" };

/** The attributes for `state`. Pass `tick` (any counter) for `live`: each change replays the tick. */
export function useStateMotion(state: MotionState, tick?: number): MotionAttrs {
  const parity = useRef<"a" | "b">("a");
  const last = useRef(tick);
  if (tick !== undefined && tick !== last.current) {
    last.current = tick;
    parity.current = parity.current === "a" ? "b" : "a";
  }
  return tick === undefined ? { "data-motion": state } : { "data-motion": state, "data-tick": parity.current };
}

/** True while `ts` (ms epoch) is younger than `windowMs`; re-renders when it ages out. */
export function useRecent(ts: number | undefined, windowMs = 3000): boolean {
  const [, force] = useState(0);
  const fresh = !!ts && Date.now() - ts < windowMs;
  useEffect(() => {
    if (!fresh || !ts) return;
    const id = window.setTimeout(() => force((n) => n + 1), windowMs - (Date.now() - ts) + 20);
    return () => window.clearTimeout(id);
  }, [fresh, ts, windowMs]);
  return fresh;
}

/** `done` for `ms` after `ts`, then `idle`: a finished thing settles. */
export function settle(ts: number | undefined, ms = 1500): MotionState {
  return ts && Date.now() - ts < ms ? "done" : "idle";
}
