// Blocks on the Cast canvas (3.3.16.3, docs/STUDIO-agents.md "Blocks"): which square blocks are folded to their four
// lines (kept per lineup in this browser: a per-viewer convenience, never the lineup's file), and the block the
// inspector says (a click on a block; a click on a card or on the canvas clears it). Nothing opens on load.
import { createStore, useStore, writeLocal } from "../../../lib/store";
import { layoutStore, patchPanel } from "../../../lib/workspace/persist";
import { roles } from "../../roles/store";
import { select as selectSquare, wf } from "../workflows/store";

type State = { sel: string; folded: Record<string, string[]>; out: string; menu: string }; // out: 3.3.16.3, the agent Delete asks about
const KEY = "halo.studio.blocks.folded";

function load(): Record<string, string[]> {
  try {
    const got = JSON.parse(localStorage.getItem(KEY) || "{}");
    return got && typeof got === "object" ? got : {};
  } catch {
    return {};
  }
}

export const blocks = createStore<State>({ sel: "", folded: load(), out: "", menu: "" });
export const useMenu = (): string => useStore(blocks, (s) => s.menu);
/** A block's menu (its ⋯ button): Connect to main, When..., Disconnect, Take it off. */
export const setMenu = (ref: string): void => blocks.update(() => ({ menu: ref }));
export const useAskOut = (): string => useStore(blocks, (s) => s.out);
/** Delete on a block's agent: its block's Agents page asks "Take <bio> out?" (never a pop-up). */
export const askOut = (bio: string): void => blocks.update(() => ({ out: bio }));

export const useBlockSel = (): string => useStore(blocks, (s) => s.sel);
export const useFolded = (lineup: string): string[] => useStore(blocks, (s) => s.folded[lineup] || NONE);
const NONE: string[] = [];

export function toggleFold(lineup: string, ref: string): void {
  blocks.update((s) => {
    const cur = s.folded[lineup] || [];
    const folded = { ...s.folded, [lineup]: cur.includes(ref) ? cur.filter((r) => r !== ref) : [...cur, ref] };
    writeLocal(KEY, JSON.stringify(folded));
    return { folded };
  });
}

/** A block clicked: the inspector says it (its summary first); the card selection clears. */
export function selectBlock(ref: string): void {
  roles.update(() => ({ sel: "" }));
  blocks.update(() => ({ sel: ref, out: "" }));
  selectSquare(ref);
  if (layoutStore("roles").get().layout?.["roles-inspector"]?.collapsed) patchPanel("roles", "roles-inspector", { collapsed: false }, false);
}

export function clearBlock(): void {
  if (blocks.get().sel) blocks.update(() => ({ sel: "" }));
  if (wf.get().selected) wf.update(() => ({ selected: "", page: "summary" }));
}
