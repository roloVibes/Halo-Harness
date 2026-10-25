// What Studio shows is what is on disk, as it changes (3.2.2.0 R6): the
// server's watcher (studio/files_live.py) publishes `files_changed` when a
// lineup, bio, config.json or a canvas layout moves -- a session's model
// editing a lineup, `halo teams apply`, a bio saved from the terminal, or
// Studio's own PUT (that one finds the page already current). A page
// subscribes with `onFilesChanged(kinds, fn)`: the frames of those kinds
// that land within DEBOUNCE_MS are merged into one call (the fleet pattern,
// `later("load", 300, ...)`), so a burst of writes is one re-read.
import { onEvent } from "./events";

export type FilesKind = "lineups" | "bios" | "config" | "layouts";
/** One merged change: the kinds that moved, the names written (added or modified), the names removed. */
export type FilesChange = { kinds: FilesKind[]; names: string[]; removed: string[] };

export const DEBOUNCE_MS = 300;
const strs = (v: unknown): string[] => (Array.isArray(v) ? v.map(String) : []);

/** Call `fn` once per burst of `files_changed` frames of `kinds`; returns the unsubscribe. */
export function onFilesChanged(kinds: FilesKind | FilesKind[], fn: (c: FilesChange) => void, ms = DEBOUNCE_MS): () => void {
  const want = Array.isArray(kinds) ? kinds : [kinds];
  let timer = 0;
  let acc: FilesChange = { kinds: [], names: [], removed: [] };
  const off = onEvent("files_changed", (f) => {
    const d = (f.data || {}) as Record<string, unknown>;
    const kind = String(d.kind || "") as FilesKind;
    if (!want.includes(kind)) return;
    const names = strs(d.names);
    const removed = strs(d.removed);
    acc = {
      kinds: acc.kinds.includes(kind) ? acc.kinds : [...acc.kinds, kind],
      names: [...acc.names.filter((n) => !removed.includes(n)), ...names.filter((n) => !acc.names.includes(n))],
      removed: [...acc.removed.filter((n) => !names.includes(n)), ...removed.filter((n) => !acc.removed.includes(n))],
    };
    window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      const c = acc;
      acc = { kinds: [], names: [], removed: [] };
      fn(c);
    }, ms);
  });
  return () => {
    window.clearTimeout(timer);
    off();
  };
}

/** A text field, text area or select inside `root` has the keyboard focus: an edit may be in progress there
 *  (a typed value commits on Enter or blur, so the store does not hold it yet). */
export function editingIn(root: string): boolean {
  const el = document.activeElement as HTMLElement | null;
  if (!el || !/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return false;
  return !!el.closest(`[data-testid="${root}"]`);
}
