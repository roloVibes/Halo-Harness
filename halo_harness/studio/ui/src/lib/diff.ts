// Structural sharing for polled JSON (3.0.7.0 R3, the Design
// pollers): `same(prev, next)` keeps the previous value when the new one is
// equal (so a store update with it is a no-op and nothing re-renders), and
// `reuse(prev, next)` keeps every unchanged row of a list by its `id`, so a
// list where one row changed re-renders that row only (rows are memoised by
// identity).

export function equal(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch {
    return false;
  }
}

/** `prev` when `next` is equal to it, else `next`. */
export function same<T>(prev: T, next: T): T {
  return equal(prev, next) ? prev : next;
}

/** `next` with every row equal to the previous row of the same id swapped for that previous row;
 *  `prev` itself when nothing changed. */
export function reuse<T extends { id: string }>(prev: T[], next: T[]): T[] {
  if (prev === next) return prev;
  const old = new Map(prev.map((r) => [r.id, r]));
  let changed = prev.length !== next.length;
  const out = next.map((r, i) => {
    const p = old.get(r.id);
    const keep = p !== undefined && equal(p, r) ? p : r;
    if (keep !== prev[i]) changed = true;
    return keep;
  });
  return changed ? out : prev;
}

/** A store patch with only the keys whose value changed (each through `same`). */
export function changed<S extends object>(prev: S, next: Partial<S>): Partial<S> {
  const out: Partial<S> = {};
  for (const k of Object.keys(next) as (keyof S)[]) {
    const v = next[k] as S[keyof S];
    if (!equal(prev[k], v)) out[k] = v;
  }
  return out;
}
