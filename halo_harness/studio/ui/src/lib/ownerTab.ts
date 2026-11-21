// A tab that can only look (3.6.0.6 P, the owner's point 31: "harness level guard 'owners page' is blocking!"). Studio
// gives the owner proof only to a page the person opened or reloaded himself (studio/owner_proof.py; lib/owner.ts); a
// tab a link or a script opened can look but not change things. Its way out is one press: "Make this tab yours"
// reloads the tab, and the person's own reload gets the proof (the rule itself does not change). The words a person
// reads, the one test of a refused write, and the one signal of it (lib/api.ts -> lib/ui/Toast.tsx). No imports: the
// server's sentence is pinned against studio/owner_proof.py NEEDS_OWNER by tests/test_studio_owner_proof.py.

export const TAB_LINE = "This tab can look but not change things, because a link or a script opened it.";
export const MAKE_YOURS = "Make this tab yours";
export const MAKE_YOURS_HOVER = "Reloads this tab; after that it can change things.";
export const GLANCE_LINK_HOVER = "Opens Studio here; press Make this tab yours there to change things.";
/** The server's refusal of a write without the proof, word for word (studio/owner_proof.py NEEDS_OWNER). */
// prettier-ignore
export const NEEDS_OWNER = "this page can look but not change things: only a Studio tab you opened or reloaded yourself may. In Studio, press Make this tab yours (it reloads the tab), or run `halo studio`.";
const LEAD = NEEDS_OWNER.slice(0, NEEDS_OWNER.indexOf(" In Studio,"));

/** Whether `text` (a toast's, an error's: with a view's prefix or not) is the server's refusal of a write. */
export function isOwnerRefusal(text: string): boolean {
  return !!text && text.includes(LEAD);
}

const heard = new Set<() => void>();

/** lib/api.ts: the shell's own write was refused for want of the proof. */
export function ownerRefused(): void {
  heard.forEach((fn) => fn());
}

/** lib/ui/Toast.tsx: the one toast of a refused write. */
export function onOwnerRefused(fn: () => void): () => void {
  heard.add(fn);
  return () => heard.delete(fn);
}
