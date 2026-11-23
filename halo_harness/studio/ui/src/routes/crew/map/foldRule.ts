// 3.6.0.15 L8 (with R1's last clause): when one of Auto's groups folds to its head. A group folds only when EVERY member
// is raw `done` (groupWords' `isAllDone`: a failed or a stopped member keeps it open, so does anything live), FOLD_S
// seconds after its last end. An end this page did not see (`ended` 0: it ended before the page loaded, or was first
// seen ended) counts as long past, so such a group is folded from its first draw. Nothing folds or unfolds while the
// drawing is held (hold.ts: the pointer on it or a sheet open): the re-flow waits for the hold, as every re-flow does.
// Pure: no React, no DOM, no store, no clock of its own (the drawing's one clock ticks it; tests/test_map_groups.py).
import { isAllDone } from "./groupWords";
import type { AutoGroup } from "./overlayGroups";

/** The same ten seconds as fleet/store.ts DONE_MS and crew/live/now.ts LINGER_MS (written out: node runs this file). */
export const FOLD_S = 10;

/** The greatest end this page saw among the members (seconds), -Infinity when it saw none. */
export function lastEnd(g: AutoGroup): number {
  return g.members.reduce((t, m) => (Number(m.ended) > 0 ? Math.max(t, Number(m.ended)) : t), -Infinity);
}

/** The group is folded at `now` (seconds; 0 = no clock yet, never folded). */
export function foldsAt(g: AutoGroup, now: number): boolean {
  return now > 0 && isAllDone(g) && now - lastEnd(g) >= FOLD_S;
}

/** The fold to draw now: the first draw takes the rule at once; after that a held drawing keeps the last answer. */
export function foldNext(was: boolean | undefined, g: AutoGroup, now: number, held: boolean): boolean {
  return was === undefined ? foldsAt(g, now) : held ? was : foldsAt(g, now);
}
