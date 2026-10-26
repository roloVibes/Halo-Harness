// The doors into Setup (3.3.0.0 R4, studio/setup_door.py): `halo init` opens
// `?mode=setup&first=1`, `halo setup team` and `/setup team` open
// `?mode=setup&block=team`. The first run opens the section's help once, titled
// "What this page does", and the status strip says "set up this box" for this
// page; a block is brought back if it was collapsed, scrolled into view and
// focused. Both words leave the address bar once read (a reload does not open
// the help again; the token in the fragment stays). A Studio page already open
// gets the same as a `focus` frame {mode: "setup", block, first} (shell/edit.ts).
import { createStore, goSection, openHelp, useStore } from "../../lib/store";
import { focusPanel, layoutStore, patchPanel } from "../../lib/workspace/persist";

/** The door's block words (setup_door.py BLOCKS) and the panel each one is. */
export const BLOCK_PANEL: Record<string, string> = {
  providers: "setup-providers",
  local: "setup-local",
  model: "setup-model",
  permissions: "setup-permissions",
  theme: "setup-theme",
  team: "setup-team",
  roles: "setup-team",
  linux: "setup-linux",
  check: "setup-check",
};

export type Door = { block?: string; first?: boolean };

/** `first`: this page was opened by `halo init` (the strip says "set up this box"). */
export const setupDoor = createStore<{ first: boolean }>({ first: false });

export function useFirstRun(): boolean {
  return useStore(setupDoor, (s) => s.first);
}

/** `?tour=off` (captures, tests) keeps the help shut, as it keeps every first-visit welcome. */
const NO_TOUR = typeof location !== "undefined" && /[?&]tour=off\b/.test(location.search);

/** Bring a block's panel back (when it was collapsed) and focus it: the panel scrolls itself into view. */
export function openBlock(id: string): void {
  if (layoutStore("setup").get().layout?.[id]) patchPanel("setup", id, { collapsed: false }, false);
  focusPanel("setup", id);
}

/** Run `fn` once Setup's panels are laid out (a page that just loaded mounts them a moment later). */
function whenLaidOut(fn: () => void, tries = 80): void {
  if (layoutStore("setup").get().layout || tries <= 0) fn();
  else window.setTimeout(() => whenLaidOut(fn, tries - 1), 50);
}

/** Open Setup the way the door asked: the section, the first run's help, the block in view. */
export function applyDoor(d: Door): void {
  goSection("setup");
  if (d.first) {
    setupDoor.update(() => ({ first: true }));
    if (!NO_TOUR) openHelp("setup", true, true);
  }
  const id = BLOCK_PANEL[String(d.block || "").toLowerCase()];
  if (id) whenLaidOut(() => openBlock(id));
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
    /* a browser that keeps the address as it is: the help opens again on a reload */
  }
  return d;
}
