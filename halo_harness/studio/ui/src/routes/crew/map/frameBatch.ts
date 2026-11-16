// R49: the map frames that arrive within one animation frame are merged into one update (one draw, not one per frame).
// An animation-frame callback waits while the tab is hidden, so a timer flushes as well: whichever runs first takes the
// queue, the other finds it empty. A Studio tab left in the background never piles frames up past one timer's worth.
export type Clock = { raf?: (f: () => void) => unknown; timer: (f: () => void, ms: number) => unknown; hidden: () => boolean };
export const FALLBACK_MS = 250;

/** A `push` that queues one item and hands every queued item to `apply` once, in order. */
export function batcher<T>(apply: (got: T[]) => void, c: Clock): (x: T) => void {
  let queue: T[] = [];
  const flush = (): void => {
    const got = queue;
    queue = [];
    if (got.length) apply(got);
  };
  return (x: T) => {
    queue.push(x);
    if (queue.length !== 1) return;
    if (c.raf && !c.hidden()) c.raf(flush);
    c.timer(flush, FALLBACK_MS);
  };
}
