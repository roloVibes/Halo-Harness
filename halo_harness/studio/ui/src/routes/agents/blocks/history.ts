// One Undo / Redo for the Cast canvas (3.3.16.3, docs/STUDIO-blocks.md "Undo"): the lineup's own edits stay the editor's
// history (roles/actions.ts `edit`, the mapping before each one), and a block's write that goes to another file -- a
// square of yours, config `workflows.*`, a block's spot -- is a step here, with the call that puts it back and the call
// that does it again. Each lineup edit and each step takes a number in one sequence, so Ctrl+Z (and the bar's Undo)
// walks back whichever came last, and Redo whichever was undone last. A lineup edit a block op saved at once (a tier
// template, a bio dropped into a tier) is remembered, so its Undo saves too: the file follows the canvas.
import { createStore, toast, useStore } from "../../../lib/store";
import { say } from "./note";

export type Step = { label: string; undo: () => Promise<string>; redo: () => Promise<string>; seq: number };
type State = { past: Step[]; future: Step[]; busy: boolean };

const MAX = 50;
let seq = 0;
let rawPast: number[] = [];
let rawFuture: number[] = [];
const saved = new WeakSet<object>();

export const steps = createStore<State>({ past: [], future: [], busy: false });
export const useStepsAny = (): { undo: boolean; redo: boolean } =>
  useStore(steps, (s) => (s.past.length ? (s.future.length ? BOTH : UNDO) : s.future.length ? REDO : NONE));
const BOTH = { undo: true, redo: true }, UNDO = { undo: true, redo: false }, REDO = { undo: false, redo: true }, NONE = { undo: false, redo: false };

/** A block write done: its step joins the history (the redo side clears). */
export function pushStep(label: string, undo: () => Promise<string>, redo: () => Promise<string>): void {
  steps.update((s) => ({ past: [...s.past, { label, undo, redo, seq: ++seq }].slice(-MAX), future: [] }));
}

/** roles/actions.ts: a lineup edit joined its history. */
export function markRaw(): void {
  rawPast = [...rawPast, ++seq].slice(-MAX);
  rawFuture = [];
}
/** A lineup edit a block op saved at once: its Undo and Redo save too. */
export function markSaved(raw: object | null): void {
  if (raw) saved.add(raw);
}
export const isSaved = (raw: object | null | undefined): boolean => !!raw && saved.has(raw);
export function rawUndone(): void {
  const top = rawPast.at(-1);
  if (top === undefined) return;
  rawPast = rawPast.slice(0, -1);
  rawFuture = [top, ...rawFuture];
}
export function rawRedone(): void {
  const head = rawFuture[0];
  if (head === undefined) return;
  rawFuture = rawFuture.slice(1);
  rawPast = [...rawPast, head];
}

/** Is the newest thing to undo a block step (not a lineup edit)? */
export function blockUndoNext(): boolean {
  const top = steps.get().past.at(-1);
  return !!top && top.seq > (rawPast.at(-1) ?? -1);
}
export function blockRedoNext(): boolean {
  const head = steps.get().future[0];
  return !!head && (rawFuture.length === 0 || head.seq < rawFuture[0]);
}

async function walk(back: boolean): Promise<void> {
  const s = steps.get();
  const step = back ? s.past.at(-1) : s.future[0];
  if (!step || s.busy) return;
  steps.update(() => ({ busy: true }));
  try {
    const line = await (back ? step.undo() : step.redo());
    steps.update((x) => (back ? { past: x.past.slice(0, -1), future: [step, ...x.future] } : { past: [...x.past, step], future: x.future.slice(1) }));
    say(`${back ? "Undone" : "Redone"}: ${line || step.label}`);
  } catch (e) {
    toast(`${back ? "Undo" : "Redo"} did not take: ${(e as Error).message || e}`, "error", 5000);
  } finally {
    steps.update(() => ({ busy: false }));
  }
}
export const undoStep = (): Promise<void> => walk(true);
export const redoStep = (): Promise<void> => walk(false);
