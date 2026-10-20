// A stable colour per agent (3.1.5.0 R3): the order this page first saw it,
// round the harness ramp of fleet.css read through data-hc (0, 1, 3, 4, 5,
// 6; 2 is the green that means "done", so no agent wears it). Session's Live
// tags, Cost's share bar and its agent rows use the same one.
const RAMP = [0, 1, 3, 4, 5, 6];
const seen = new Map<string, number>();

export function hueOf(key: string): number {
  if (!seen.has(key)) seen.set(key, seen.size % RAMP.length);
  return RAMP[seen.get(key)!];
}
