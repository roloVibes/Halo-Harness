// The palette's Roles group (3.0.7.0 R2): a new lineup, apply the open one,
// a new bio, test the open bio's model (or the selected card's), add a tier
// (3.1.6.0 R1), save, undo, redo, and open any lineup or bio by name.
import { goSection, toast } from "../../lib/store";
import { focusPanel } from "../../lib/workspace/persist";
import { redo, save, undo } from "./actions";
import { openBio, testModel } from "./bioActions";
import { showBio } from "./Assignment";
import { nodeById, openDialog, roles, setView } from "./store";
import { openLineup, startRoles } from "./sync";

export type RolesCommand = { id: string; group: string; label: string; hint?: string; kbd?: string; run: () => void };

function inRoles(fn: () => void): () => void {
  return () => {
    goSection("roles");
    startRoles();
    window.setTimeout(fn, 60);
  };
}

/** The model "Roles: test model" probes: the open bio's preference, else the selected card's model. */
function modelToTest(): string {
  const s = roles.get();
  const pref = (s.bioDraft?.models as { preference?: string } | undefined)?.preference;
  return String(pref || nodeById(s, s.sel)?.model || "");
}

export function rolesCommands(): RolesCommand[] {
  const s = roles.get();
  const g = "Roles";
  const open = s.name;
  const out: RolesCommand[] = [
    { id: "roles-new-lineup", group: g, label: "Roles: new lineup", hint: "your own copy of a lineup, opened on the canvas", run: inRoles(() => openDialog({ kind: "new-lineup", from: open || "balanced" })) },
    { id: "roles-apply", group: g, label: "Roles: apply lineup", hint: open ? `make ${open} the lineup new sessions use (asks first)` : "open a lineup first",
      run: inRoles(() => (!open ? toast("Open a lineup first (Lineups)", "info") : roles.get().dirty ? toast("Save first: Apply uses the saved file", "info") : openDialog({ kind: "apply" }))) },
    { id: "roles-new-bio", group: g, label: "Roles: new bio", hint: "an agent bio from a shipped one", run: inRoles(() => openDialog({ kind: "new-bio", from: roles.get().bio || "general" })) },
    { id: "roles-test-model", group: g, label: "Roles: test model", hint: "a one-token probe of the open bio's (or the selected card's) model",
      run: inRoles(() => {
        const ref = modelToTest();
        if (!ref) return toast("Open a bio or select a card first: its model is what gets tested", "info");
        void testModel(ref).then((p) => p && toast(p.ok ? `${ref}: ok in ${p.latency_ms} ms` : `${ref}: ${p.error}`, p.ok ? "done" : "error", 5000));
        const bio = roles.get().bio || nodeById(roles.get(), roles.get().sel)?.agent;
        if (bio) showBio(bio);
      }) },
    // 3.1.6.0 R1: the canvas bar's Add tier name field, opened from the palette
    { id: "roles-add-tier", group: g, label: "Roles: add tier", hint: open ? `a new tier box on ${open}'s canvas: name it, then drag cards in` : "open a lineup first",
      // the field opens once the canvas panel took the focus (a field that loses it while empty closes)
      run: inRoles(() => (!open ? toast("Open a lineup first (Lineups)", "info") : (setView("workspace"), focusPanel("roles", "roles-graph"),
        void window.setTimeout(() => roles.update(() => ({ tierAdd: true })), 120)))) },
    { id: "roles-save", group: g, label: "Roles: save lineup", kbd: "Mod+S", hint: open ? `write ${open} to your scope` : "open a lineup first", run: inRoles(() => void save()) },
    { id: "roles-undo", group: g, label: "Roles: undo", kbd: "Ctrl+Z", hint: `${s.past.length} edit${s.past.length === 1 ? "" : "s"} to undo`, run: inRoles(() => void undo()) },
    { id: "roles-redo", group: g, label: "Roles: redo", kbd: "Ctrl+Shift+Z", run: inRoles(() => void redo()) },
  ];
  for (const l of s.lineups.slice(0, 40))
    out.push({ id: "roles-open-" + l.name, group: g, label: `Roles: open lineup ${l.name}`, hint: [l.active ? "active" : "", l.scope === "template" ? "shipped" : l.scope, l.description].filter(Boolean).join(" · "),
      run: inRoles(() => (setView("workspace"), void openLineup(l.name), focusPanel("roles", "roles-graph"))) });
  for (const b of s.bios.slice(0, 40))
    out.push({ id: "roles-bio-" + b.name, group: g, label: `Roles: bio ${b.name}`, hint: [b.kind, b.model].filter(Boolean).join(" · "), run: inRoles(() => (setView("workspace"), void openBio(b.name), showBio(b.name))) });
  return out;
}
