// Where an agent or a workflow comes from, in the words a person reads (3.6.0.6 P, the owner's point 31): the ONE place
// a row's scope becomes its tag ("this project's", "ships with Halo", "pack {id}"), and the rule that an item that ships
// with Halo or comes from a pack is read-only here (Copy makes it yours, named as crew/store.py `own_copy` names it).
// The Workflows and Agents lists, their forms' pickers and the Map's add list all ask here.
import type { Scope } from "./types";

/** The pack an item comes from: the part of its name before `--` (`doc-review--review-docs` -> `doc-review`). */
export const packOf = (name: string): string => (name.includes("--") ? name.split("--")[0] : "");

/** The tag of a row ("" for one of yours). */
export function scopeTag(scope: Scope | string, name: string): string {
  if (scope === "project") return "this project's";
  if (scope === "starter") return "ships with Halo";
  if (scope === "pack") return `pack ${packOf(name)}`;
  return "";
}

/** Ships with Halo or comes from a pack: read here, never saved over or deleted. */
export const readOnly = (scope: Scope | string | undefined): boolean => scope === "starter" || scope === "pack";

/** A pack's item's line in its form (the API refuses a write of it with the same sentence: crew/store.py PACK_READ_ONLY). */
export const packReadOnly = (name: string): string => `From the pack ${packOf(name)}: read-only here. Copy makes it yours.`;

/** The stem of a copy's name: `my-` and its own part for one that ships with Halo or comes from a pack, else `-copy`. */
export const copyStem = (name: string, scope: Scope | string | undefined): string =>
  readOnly(scope) ? `my-${name.split("--").pop()}` : `${name}-copy`;
