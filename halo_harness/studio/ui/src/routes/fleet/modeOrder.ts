// 3.4.1.0 R6: which permission mode a session's row shows (Session's mode word), whatever order its two sources land
// in. A `status` frame says the mode as the session moved it (Shift+Tab, /plan); GET fleet says the registry's, which
// the session's runtime writes a moment after that frame. So:
// - a status frame older than one already applied (the session's own `ts`) never puts its mode back;
// - a GET answer asked BEFORE the newest status frame landed may have been read before the registry moved: the
//   frame's mode stays over it; an answer asked after it lands wins (the registry is the truth then, frame or not).
// No imports: tests/test_studio_mode_order.py runs it under node.

/** The newest status frame's mode for one session: the session's own time (s) and when it landed here (ms). */
export type ModeSeen = { mode: string; ts: number; at: number };

/** A status frame's mode lands: the next ModeSeen, or `prev` (and `apply` false) when the frame is older than it. */
export function frameMode(prev: ModeSeen | undefined, mode: string, ts: number, at: number): { seen: ModeSeen | undefined; apply: boolean } {
  if (!mode) return { seen: prev, apply: false };
  if (prev && Number.isFinite(ts) && Number.isFinite(prev.ts) && ts < prev.ts) return { seen: prev, apply: false };
  return { seen: { mode, ts: Number.isFinite(ts) ? ts : prev?.ts ?? 0, at }, apply: true };
}

/** The mode a GET answer asked at `asked` (ms) shows: its own, unless the newest frame landed after it was asked. */
export function answerMode(got: string | null | undefined, seen: ModeSeen | undefined, asked: number): string | null | undefined {
  return seen && seen.at >= asked ? seen.mode : got;
}
