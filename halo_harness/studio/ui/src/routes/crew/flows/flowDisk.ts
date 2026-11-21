// Agents -> 2 · Workflows follows the disk (3.6.0.9 V, the owner's point 34): the workflow open in the form is the one
// on disk, whoever wrote it -- a session's Builder card, its plain Edit or Write, a hand. Studio's watcher names the
// files that moved, each with the hash of its file (studio/files_live.py); the form holds the hash of the file it was
// read from or saved to (`sig`), so its own Save, coming back 1.5 s later, reads nothing and says nothing. Otherwise:
// - no unsaved edit: the workflow is read again in place (`openFlow`), the form shows the new steps and words;
// - an unsaved edit: nothing of his changes; the form says so (`stale`: "{name} changed on disk while you had edits
//   here. Save writes yours over it." with "Reload it (your edits go)");
// - its file removed: his form stays (it is his text) with "{name} was removed on disk. Save writes it again." (`gone`);
// - a pack's workflow (read-only here) follows its pack: read again on `pack_changed` when it differs.
import { api } from "../../../lib/api";
import { onEvent } from "../../../lib/events";
import type { FilesChange } from "../../../lib/filesLive";
import type { Workflow } from "../types";
import { flowDirty, flows, followWith, openFlow } from "./flowStore";

export const staleLine = (name: string): string => `${name} changed on disk while you had edits here. Save writes yours over it.`;
export const goneLine = (name: string): string => `${name} was removed on disk. Save writes it again.`;

/** The open workflow `name` changed on disk; `sig` the file's hash when the frame carried it (a read is then made only
 *  when it differs from what the form holds). */
export async function changedOnDisk(name: string, sig?: string): Promise<void> {
  const s = flows.get();
  if (!s.form || !s.open?.name || s.open.name !== name) return;
  if (sig && sig === s.sig) return; // what the form holds IS what is on disk (its own Save, coming back)
  if (flowDirty(s)) return void flows.update(() => ({ stale: true, gone: false }));
  await openFlow(name, s.open.scope);
}

function removedOnDisk(name: string): void {
  const s = flows.get();
  if (!s.form || !s.open?.name || s.open.name !== name || s.open.scope === "pack") return;
  flows.update(() => ({ gone: true, stale: false, saved: null, sig: "" })); // Save is his to press: it writes it again
}

followWith((c: FilesChange) => {
  for (const n of c.removed) removedOnDisk(n);
  for (const k of Object.keys(c.sigs)) if (k.startsWith("workflows:")) void changedOnDisk(k.slice(10), c.sigs[k]);
});

const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** A pack's workflow open in the form: its pack changed (enable, update...): read again only when it differs. */
onEvent("pack_changed", async () => {
  const s = flows.get();
  if (!s.form || s.open?.scope !== "pack" || !s.open.name) return;
  const name = s.open.name;
  try {
    const r = await api.get<{ workflow: Workflow; sig?: string }>(`crew/workflow/${encodeURIComponent(name)}`, { scope: "pack" });
    const now = flows.get();
    if (now.open?.name !== name || (r.sig && r.sig === now.sig)) return;
    const saved = now.saved;
    if (saved && same([r.workflow.for || "", r.workflow.steps || []], [saved.for || "", saved.steps || []])) return;
    await changedOnDisk(name);
  } catch {
    /* the pack is gone or unreadable: the form stays as it is */
  }
});
