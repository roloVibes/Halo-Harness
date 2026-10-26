// The doors into Setup (3.3.0.0 R4, studio/setup_door.py): `halo init` opens
// `?mode=setup&first=1`, `halo setup team` and `/setup team` open
// `?mode=setup&block=team`. 3.3.1.0 R1: nothing opens on its own -- the first
// run only leads the rail's summary line with "set up this box" (the help
// stays the ? in the header), and a block word opens that step's page
// (pages.ts; `summary` too). Both words leave the address bar once read (a
// reload opens the page plainly; the token in the fragment stays). A Studio
// page already open gets the same as a `focus` frame {mode: "setup", block,
// first} (shell/edit.ts).
import { createStore, goSection, useStore } from "../../lib/store";
import { goto, stepOf } from "./pages";

export type Door = { block?: string; first?: boolean };

/** `first`: this page was opened by `halo init` (the rail's summary says "set up this box"). */
export const setupDoor = createStore<{ first: boolean }>({ first: false });

export function useFirstRun(): boolean {
  return useStore(setupDoor, (s) => s.first);
}

/** Open the page of a door's block word (`roles` is Team); a word that is no step changes nothing. */
export function openBlock(word: string): void {
  const s = stepOf(word);
  if (s) goto(s);
}

/** Open Setup the way the door asked: the section, the first run's line, the block's page. */
export function applyDoor(d: Door): void {
  goSection("setup");
  if (d.first) setupDoor.update(() => ({ first: true }));
  if (d.block) openBlock(d.block);
}

/** The page's own address: `?mode=setup` with `first=1` or `block=`; both words are read once, then dropped. */
export function doorFromUrl(): Door | null {
  if (typeof location === "undefined") return null;
  const q = new URLSearchParams(location.search);
  if (q.get("mode") !== "setup" || (!q.has("first") && !q.has("block"))) return null;
  const d: Door = { first: q.get("first") === "1", block: q.get("block") || "" };
  q.delete("first");
  q.delete("block");
  try {
    const rest = q.toString();
    history.replaceState(history.state, "", location.pathname + (rest ? `?${rest}` : "") + location.hash);
  } catch {
    /* a browser that keeps the address as it is: the words are read again on a reload */
  }
  return d;
}
