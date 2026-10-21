// What a pack's row does in Lineups and Bios (3.2.0.0 R2, studio/packs_roles_api.py):
// Preview opens it read-only (a lineup on the canvas, a bio in the form; the
// Inspector says "from pack <id>, read-only"), Clone copies it into your
// scope as <name> (the <id>-- dropped) with a `from_pack` line, Customize is
// Clone and then the copy opened, Apply is the existing Apply dialog for it.
// Clone never writes into a file of yours: a 409 opens the clone-exists
// dialog (replace yours, or pick another name), which alone sends `replace`.
import { api, ApiError } from "../../lib/api";
import { toast } from "../../lib/store";
import { focusPanel } from "../../lib/workspace/persist";
import { openBio } from "./bioActions";
import { closeDialog, openDialog, roles, setTab } from "./store";
import { loadLists, msg, openLineup } from "./sync";

type Cloned = { ok: boolean; name: string; path: string; from_pack: string; replaced: boolean };
type Kind = "bio" | "lineup";

export async function openCopy(what: Kind, name: string): Promise<void> {
  if (what === "lineup") {
    await openLineup(name, true);
    roles.update(() => ({ view: "workspace" }));
    if (roles.get().tab !== "lineup") setTab("lineup");
    focusPanel("roles", "roles-inspector");
  } else {
    await openBio(name);
    focusPanel("roles", "roles-bios");
  }
}

/** Clone (open: Customize) `name`, a pack's bio or lineup; `as` names the copy, `replace` comes from the confirm only. */
export async function cloneFromPack(what: Kind, name: string, open: boolean, opts: { as?: string; replace?: boolean } = {}): Promise<boolean> {
  roles.update(() => ({ busy: "clone" }));
  try {
    const r = await api.post<Cloned>("roles/clone", { kind: what, name, as: opts.as || undefined, replace: opts.replace || undefined }, { scope: roles.get().scope });
    closeDialog();
    toast(`${name} ${r.replaced ? "replaced your" : "copied to your"} ${what} ${r.name} (from pack ${r.from_pack})${open ? "" : ": Customize opens it"}`, "done", 4000);
    await loadLists();
    if (open) await openCopy(what, r.name);
    return true;
  } catch (e) {
    const d = e instanceof ApiError ? e.data : {};
    if (e instanceof ApiError && e.status === 409 && d.exists) {
      openDialog({ kind: "clone-exists", what, name, target: String(d.name || ""), shipped: !!d.shipped, error: String(d.error || e.message), open });
    } else {
      toast(`Not cloned: ${msg(e)}`, "error", 5000);
    }
    return false;
  } finally {
    roles.update(() => ({ busy: "" }));
  }
}

/** Apply a pack's lineup: open it (read-only), then the existing Apply dialog, which names the pack. */
export async function applyFromPack(name: string): Promise<void> {
  if (roles.get().name !== name) await openLineup(name);
  if (roles.get().name === name) openDialog({ kind: "apply" });
}
