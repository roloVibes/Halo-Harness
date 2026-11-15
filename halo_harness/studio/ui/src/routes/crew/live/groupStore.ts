// Live in groups (3.3.16.3): which group boxes are folded to their title bar (a chevron on the bar, or Enter on the
// bar), and whether Session's timeline lists its lanes by group. Kept for the page's life, per group id; nothing opens or
// folds by itself.
import { createStore, useStore } from "../../../lib/store";

type State = { closed: string[]; byGroup: boolean };
export const groupState = createStore<State>({ closed: [], byGroup: false });

export function toggleGroup(id: string): void {
  groupState.update((s) => ({ closed: s.closed.includes(id) ? s.closed.filter((x) => x !== id) : [...s.closed, id] }));
}

export function useClosed(): string[] {
  return useStore(groupState, (s) => s.closed);
}

export function useByGroup(): boolean {
  return useStore(groupState, (s) => s.byGroup);
}

export function toggleByGroup(): void {
  groupState.update((s) => ({ byGroup: !s.byGroup }));
}
