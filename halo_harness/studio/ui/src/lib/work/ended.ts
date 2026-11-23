// When an agent ended, in seconds (3.6.0.15 F4). It exists because the page's own sighting of an end (the feed's
// doneAt, set when a frame's state differs from one the page already held) misses every helper the page first saw
// already ended: it started and ended between two reads, or its frames came before its session was listed. Such a
// helper drew no "done in {span}" at all. A helper's row now carries its own `ended` (agent/agent_observe.py, written
// with the end state); main's row never does (its `since` is the session's start), so main keeps the page's doneAt.
// Pure: no React, no store (tests/test_auto_groups.py runs it in node).
/** The states that have ended (the record's live count reads them too). */
export const FINISHED = ["done", "failed", "stopped"];

/** A finished state's end: the row's own `ended` when it is a finite number, else the page's doneAt (ms), else null;
 *  any other state: null. */
export function endedOf(state: string, rowEnded: unknown, doneAtMs: number | undefined): number | null {
  if (!FINISHED.includes(state)) return null;
  if (typeof rowEnded === "number" && isFinite(rowEnded)) return rowEnded;
  return doneAtMs ? doneAtMs / 1000 : null;
}
