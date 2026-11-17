// A door's ask kept until its section is laid out (3.6.0.2 P4 batch 9: a door never leads nowhere). A door switches
// section and asks a panel to open in the same step; on that section's first visit its workspace has no layout yet (it
// is stored in Workspace's effect, after its first commit). `patchPanel` / `showPanel` (persist.ts) keep the ask here and
// apply it at the section's first layout: one ask per panel, the last wins, in the order asked. Nothing is kept across a
// page load. Pure: node-tested (tests/test_studio_door_kept.py).

const asks = new Map<string, Map<string, () => void>>();

/** Keep `go` for panel `id` of `section` (an earlier ask for the same panel is replaced: the last wins). */
export function keepAsk(section: string, id: string, go: () => void): void {
  let m = asks.get(section);
  if (!m) asks.set(section, (m = new Map()));
  m.delete(id); // the last ask goes last
  m.set(id, go);
}

/** The asks kept for `section`, in the order asked, taken out (each runs once). */
export function takeAsks(section: string): (() => void)[] {
  const m = asks.get(section);
  if (!m) return [];
  asks.delete(section);
  return [...m.values()];
}

/** How many asks wait for `section` (tests). */
export const keptFor = (section: string): string[] => [...(asks.get(section)?.keys() || [])];
