// What a coach card's Edit does (3.0.9.0 R3 Apply; 3.1.3.0 R1 renamed it Edit, Apply now writes after a confirm,
// lib/coach/actions.ts), for every report face: it
// opens the editor that owns the field with the change filled in and marked,
// and saves nothing. A bio target opens Roles on that bio's form (the field
// set in the draft, the bio's note naming it; Save bio keeps it); a lineup
// target opens the lineup with the role's model changed in the draft and the
// Inspector on its Lineup tab; a plan target opens the plan editor on the
// run's plan with the edit staged (plan/stage.ts).
import type { Suggestion } from "../../lib/coach/types";
import { goSection, toast } from "../../lib/store";
import { focusPanel } from "../../lib/workspace/persist";
import { edit } from "../roles/actions";
import { editBio, openBio } from "../roles/bioActions";
import { getPath, setPath } from "../roles/sections";
import { agentsOf, roles, setView } from "../roles/store";
import { loadLists, openLineup } from "../roles/sync";
import { stagePlan } from "./plan/stage";

const shown = (v: unknown) => (Array.isArray(v) ? v.join(", ") : String(v));

/** A prompt note goes after the bio's own notes (once); every other field takes the value. */
function merged(field: string, cur: unknown, value: unknown): unknown {
  if (field.endsWith("prompt_notes") && typeof cur === "string" && cur.trim() && typeof value === "string") {
    return cur.includes(value) ? cur : `${cur.trim()}\n${value}`;
  }
  return value;
}

async function toBio(s: Suggestion, run: string): Promise<void> {
  const a = s.apply!;
  goSection("roles");
  setView("workspace");
  if (!roles.get().loaded) await loadLists();
  roles.update(() => ({ coachHint: { bio: a.name, field: a.field, value: a.value, run, text: s.text } }));
  await openBio(a.name);
  if (roles.get().bio !== a.name || !roles.get().bioDraft) {
    toast(`Roles could not open bio ${a.name}`, "error", 5000);
    return;
  }
  editBio((raw) => setPath(raw, a.field, merged(a.field, getPath(raw, a.field), a.value)));
  focusPanel("roles", "roles-bios");
  toast(`Bio ${a.name}: ${a.field} = ${shown(a.value)} filled in. Save bio keeps it.`, "info", 6000);
}

async function toLineup(s: Suggestion, run: string): Promise<void> {
  const a = s.apply!;
  goSection("roles");
  setView("workspace");
  if (!roles.get().loaded) await loadLists();
  const name = a.name || roles.get().info?.active_team || "";
  if (name && roles.get().name !== name) await openLineup(name);
  const role = a.field.replace(/^roles\./, "");
  const entry = agentsOf(roles.get().raw).findIndex((e) => e.as === role || e.role === role);
  if (entry >= 0) {
    edit((raw) => {
      const e = agentsOf(raw)[entry];
      setPath(e, "models.preference", a.value);
    });
    const e = agentsOf(roles.get().raw)[entry];
    roles.update(() => ({ sel: String(e.as || e.role || "") }));
  }
  roles.update(() => ({ tab: "lineup", coachHint: { bio: "", field: a.field, value: a.value, run, text: s.text } }));
  focusPanel("roles", "roles-inspector");
  toast(entry >= 0 ? `Lineup ${name}: the ${role} role's model is ${shown(a.value)} in the draft. Save keeps it.`
    : `Lineup ${name || "(none active)"} has no ${role} role: give one the model ${shown(a.value)}.`, "info", 6000);
}

export function applySuggestion(s: Suggestion, run: string): void {
  const a = s.apply;
  if (!a) return;
  if (a.target === "bio") void toBio(s, run);
  else if (a.target === "lineup") void toLineup(s, run);
  else void stagePlan(run, a.field, a.value, s.text);
}
