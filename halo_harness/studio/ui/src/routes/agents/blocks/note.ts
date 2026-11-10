// The canvas's one-line result (3.3.16.3): every block drop, connection, Undo and Redo says what changed in one line over
// the canvas, until the next one or its x. And the confirm card a drop raises before it writes: WHAT it adds, what it
// COSTS, what it WRITES, then Do it / Cancel. Nothing here opens on load.
import { createStore, useStore } from "../../../lib/store";

export type Ask = { title: string; what: string; costs: string; writes: string; go: () => Promise<void>; kind: string; button: string };
type State = { line: string; tone: "done" | "error"; ask: Ask | null; busy: boolean };

export const blockNote = createStore<State>({ line: "", tone: "done", ask: null, busy: false });
export const useBlockNote = <S,>(pick: (s: State) => S): S => useStore(blockNote, pick);

export const say = (line: string, tone: "done" | "error" = "done"): void => blockNote.update(() => ({ line, tone }));
export const unsay = (): void => blockNote.update(() => ({ line: "" }));
export const ask = (a: Ask): void => blockNote.update(() => ({ ask: a }));
export const cancelAsk = (): void => blockNote.update(() => ({ ask: null }));

/** The confirm card's Do it: the write, then its line (an error says why; the card stays for another try). */
export async function confirmAsk(): Promise<void> {
  const a = blockNote.get().ask;
  if (!a || blockNote.get().busy) return;
  blockNote.update(() => ({ busy: true }));
  try {
    await a.go();
    blockNote.update(() => ({ ask: null }));
  } catch (e) {
    say((e as Error).message || "it did not save", "error");
  } finally {
    blockNote.update(() => ({ busy: false }));
  }
}
