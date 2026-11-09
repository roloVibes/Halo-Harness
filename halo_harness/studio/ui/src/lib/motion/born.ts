// 3.3.15.0 L1, the Instrument look's motion rule (PROPOSAL.md section 5): nothing moves on a section load, so the
// animations that carry meaning (a node that starts, a meter that fills, a rung that climbs) play only for a thing
// that appears after its page has drawn. `useBorn()` says so at mount: more than BORN_AFTER_MS after the page or the
// section it lives in showed. It answers [born, grown]: call `grown` from onAnimationEnd, so a section shown again
// (a hidden section's animations restart when it shows) never replays it. `ackFailed` / `failedAcked`: a failed
// node keeps its red rule and edge until it is clicked.
import { useCallback, useState } from "react";
import { studio } from "../store";

export const BORN_AFTER_MS = 2500;
const now = () => (typeof performance !== "undefined" ? performance.now() : Date.now());
let shownAt = now();
let shown = studio.get().section;
studio.subscribe(() => {
  const s = studio.get().section;
  if (s !== shown) {
    shown = s;
    shownAt = now();
  }
});

export function useBorn(): [boolean, () => void] {
  const [born, setBorn] = useState(() => now() - shownAt > BORN_AFTER_MS);
  const grown = useCallback(() => setBorn(false), []);
  return [born, grown];
}

const acked = new Set<string>();
export function ackFailed(key: string): void {
  acked.add(key);
}
export function failedAcked(key: string): boolean {
  return acked.has(key);
}
