// Which attention rows a scope lists and counts (3.6.0.5 r, the coordinator's ruling on question 10: keep the row).
// Pure (no React, no store), so tests/test_attention_doors.py runs it in node. Session's Attention lists the rows of its
// harness AND a row of no harness: one side of a conflict whose holder is in no session (live/conflicts.py), a decision
// of this machine that must stay seen, counted and answerable on Studio's main page now that Agents has no queue.
import type { AttnRow } from "./pstore";
import type { Scope } from "./store";

/** An attention row of the harness in scope, or of no harness at all. */
export const rowIn = (scope: Scope) => (r: Pick<AttnRow, "harness">): boolean => !scope.harness || !r.harness || r.harness === scope.harness;

/** The rows in scope, and how many wait (the watcher's live count when nothing narrows them). */
export function scopedRows(rows: AttnRow[], live: number | null | undefined, scope: Scope): { rows: AttnRow[]; count: number } {
  const mine = scope.harness ? rows.filter(rowIn(scope)) : rows;
  return { rows: mine, count: scope.harness ? mine.length : live ?? rows.length };
}
