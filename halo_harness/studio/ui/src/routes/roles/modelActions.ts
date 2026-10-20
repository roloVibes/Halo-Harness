// The model actions of Roles (3.1.4.0 R4): a card's own model
// (`agents[i].models.preference`, the Inspector strip's and the Assignment
// tab's ModelSelect: one edit, then Save, so `GET lineup` reads it back and
// the card's pill follows), the pill's click (the Inspector opens and its
// strip's select takes the focus), "change the bio's model" (the Bios panel
// opens on that bio with its MODELS section in view) and "open that card in
// Roles" from another section (Team's "runs on" link).
import { goSection } from "../../lib/store";
import { layoutStore, patchPanel } from "../../lib/workspace/persist";
import { forgetResolved } from "../shared/resolve";
import { edit, save } from "./actions";
import { openBio } from "./bioActions";
import { agentsOf, roles, setView } from "./store";
import { openLineup, startRoles } from "./sync";
import type { Raw } from "./types";

/** The card's own model ("" keeps its bio's), saved at once. */
export async function setSlotModel(index: number, ref: string): Promise<boolean> {
  const before = roles.get().raw;
  edit((raw) => {
    const e = agentsOf(raw)[index];
    if (!e) return;
    const over = { ...((e.models && typeof e.models === "object" ? e.models : {}) as Raw) };
    if (ref) over.preference = ref;
    else delete over.preference;
    if (Object.keys(over).length) e.models = over;
    else delete e.models;
  });
  if (roles.get().raw === before) return true;
  const ok = await save();
  if (ok) forgetResolved();
  return ok;
}

/** The pill (or Enter on the selected card): that card selected, the Inspector open, its strip's select focused. */
export function focusModel(id: string): void {
  if (id && roles.get().sel !== id) roles.update(() => ({ sel: id }));
  patchPanel("roles", "roles-inspector", { collapsed: false, face: "detail" }, false);
  roles.update(() => ({ modelFocus: "strip" }));
}

/** "change the bio's model": the Bios panel on that bio, its MODELS section (first in the form) focused. */
export function showBioModels(bio: string): void {
  if (!bio) return;
  void openBio(bio);
  patchPanel("roles", "roles-bios", { collapsed: false, face: "detail" }, false); // the select scrolls itself into view
  roles.update(() => ({ modelFocus: "bio" }));
}

export const focusDone = () => roles.update(() => ({ modelFocus: "" }));

function whenLaidOut(fn: () => void, tries = 80): void {
  if (layoutStore("roles").get().layout || tries <= 0) fn();
  else window.setTimeout(() => whenLaidOut(fn, tries - 1), 50);
}

/** From another section: Roles on `lineup`, the card `card` selected, the strip's select focused. */
export async function openCardModel(lineup: string, card: string): Promise<void> {
  goSection("roles");
  setView("workspace");
  roles.update(() => ({ editing: "card:" + lineup })); // the active lineup does not open over this one
  startRoles();
  try {
    if (lineup && roles.get().name !== lineup) await openLineup(lineup);
  } finally {
    roles.update(() => ({ editing: "" }));
  }
  whenLaidOut(() => focusModel(card));
}
