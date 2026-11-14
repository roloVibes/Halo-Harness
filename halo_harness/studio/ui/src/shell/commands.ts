// The palette's commands and its fuzzy matcher. Groups: Go to, Help, then
// the sections in the registry's order (3.3.16.0 R1: Agents -- its views, then Cast's Roles lines and Runs'
// Orchestra lines -- and Fleet; Session has none of its own), Media, View, Layout. Each
// command may show a key (the same hint the menus show; 3.3.2.0 R1: the Go to
// entries carry each section's Alt+N, which the icon rail no longer prints; 3.6.0.0 R0a: Layout's "Reset layout"
// names the section in the hint; Arrange went with the grid, and "Show panel: <name>" opens the drawer or tab). 3.2.0.0 R3: the packs' sections join Go to and
// Help, and each pack's palette actions come last in their own group ("pack <id>").
import { goSection, openHelp, studio, toast, toggleFocus, toggleRail } from "../lib/store";
import { themeCommands } from "./themeCommands"; // 3.3.12.0 R1
import { openGlossary } from "../lib/glossary";
import { setDensity } from "../lib/density";
import { layoutStore, resetLayout, showPanel, whenLaidOut } from "../lib/workspace/persist";
import type { PanelSpec } from "../lib/workspace/types";
import { sectionDef, sections, type SectionDef } from "../routes";
import { packCommands } from "../routes/packs/registry";
import { packs } from "../routes/packs/store";
import { mediaCommands } from "../routes/media/commands";
import { runCommands } from "../routes/agents/run/commands"; // 3.4.0.0 D: a goal run's lines (Runs' went)
import { fleetCommands } from "../routes/fleet/commands";
import { packPageCommands } from "../packlib/kbd"; // 3.3.13.0 R2: a pack page's own lines (api.lib.commands)
import { rolesCommands } from "../routes/roles/commands";
import { agentsCommands } from "../routes/agents/commands";
import { settingsCommands } from "../routes/settings/commands";
import { localCommands } from "../routes/local/commands";
import { promptCommand } from "../routes/session/promptStore";
import { GLANCE_HINT, openGlanceDoor } from "../routes/glance/Door";

/** `disabled`: drawn with its hint saying why (3.3.2.0 R2: nothing to arrange, nothing to reset); Enter does nothing. */
export type Command = { id: string; group: string; label: string; kbd?: string; hint?: string; disabled?: boolean; run: () => void };

/** Open a panel (a drawer, a tab, or an optional one added) and focus it, bringing the section's workspace up first. */
export function revealPanel(def: SectionDef, p: PanelSpec): void {
  def.enter?.();
  whenLaidOut(def.id, () => showPanel(def.id, p)); // the section may still be mounting (a slow runner: seconds)
}

/** What Reset layout would say when there is nothing to do ("" when there is). */
export function layoutWords(def: SectionDef): { reset: string } {
  const ls = layoutStore(def.id).get();
  const open = Object.values(ls.layout || {}).some((p) => !p.collapsed) && def.panels.some((s) => ls.layout?.[s.id] && !ls.layout[s.id].collapsed && !s.primary && s.role !== "main");
  return { reset: ls.custom || open ? "" : `${def.title}: nothing to reset, every drawer is closed` };
}

/** Reset layout (the palette and the header's ... menu): every drawer closed, widths back to their content's. */
export function resetSection(def: SectionDef): void {
  resetLayout(def.id);
  toast(`${def.title} layout reset`, "done");
}

export function commands(): Command[] {
  const cur = sectionDef(studio.get().section);
  const all = sections();
  const out: Command[] = all.map((s) => ({
    id: "go-" + s.id,
    group: "Go to",
    label: s.title,
    hint: s.blurb,
    kbd: s.kbd || undefined,
    run: () => goSection(s.id),
  }));
  const here = studio.get().section; // 3.3.16.0 R1: Agents' def is the workspace it draws (its id roles)
  for (const s of [all.find((x) => x.id === here) ?? cur, ...all.filter((x) => x.id !== here)]) {
    out.push({
      id: "help-" + s.id,
      group: "Help",
      label: `Help: how ${s.title} works`,
      hint: s.id === here ? "the steps, the panels and the keys" : s.blurb,
      kbd: s.id === here ? "?" : undefined,
      run: () => {
        goSection(s.id);
        openHelp(s.id);
      },
    });
  }
  out.push(
    { id: "help-glossary", group: "Help", label: "Help: glossary", hint: "every word Halo uses, one paragraph each", run: () => openGlossary() },
    ...themeCommands(), // 3.3.12.0 R1: follow the system, then one per palette
    { id: "density-compact", group: "View", label: "Density: compact", hint: "tighter spacing, a smaller type scale; the header's rows button", run: () => setDensity("compact") },
    { id: "density-comfortable", group: "View", label: "Density: comfortable", hint: "the default spacing and type scale", run: () => setDensity("comfortable") },
    { id: "rail", group: "View", label: "Expand or collapse the rail", hint: "the section icons, or the icons with their titles", run: toggleRail },
    { id: "glance", group: "View", label: "Open the glance", hint: GLANCE_HINT, run: openGlanceDoor }, // 3.4.1.0 R4
    { id: "focus", group: "View", label: "Focus", hint: "hide the rail, the inspector and the status bar; again brings them back", kbd: "F", run: toggleFocus },
  );
  if (!cur.paged) { // 3.3.1.0 R1: a paged section (Setup) has no layout to reset
    const w = layoutWords(cur);
    out.push({ id: "reset-layout", group: "Layout", label: "Reset layout", hint: w.reset || `${cur.title}: every drawer closed, the main thing back`, disabled: !!w.reset, run: () => resetSection(cur) });
  }
  for (const p of cur.panels) {
    out.push({
      id: "panel-" + p.id,
      group: "Layout",
      label: `Show panel: ${p.title}`,
      hint: p.role === "main" || p.primary ? "the main thing of this view" : "opens it beside the main thing; Alt+Left / Alt+Right on it: wider or narrower",
      run: () => revealPanel(cur, p),
    });
  }
  out.push(promptCommand()); // 3.3.11.0 R1: Session's Prompt panel, Alt+Enter
  out.push(...agentsCommands(), ...rolesCommands(), ...runCommands(), ...fleetCommands(), ...mediaCommands());
  out.push(...settingsCommands()); // 3.3.3.0 R2: "Settings: <title>", one per config key
  out.push(...localCommands()); // 3.3.5.0 R1: "Local: <page>", one per page
  out.push(...packCommands(packs.get().reg), ...packPageCommands());
  return out;
}

/** Subsequence match: -1 for no match, higher is better (word starts and runs score). */
export function fuzzy(query: string, text: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 0;
  const t = text.toLowerCase();
  let score = 0;
  let ti = 0;
  let run = 0;
  for (const ch of q) {
    if (ch === " ") continue;
    const at = t.indexOf(ch, ti);
    if (at < 0) return -1;
    run = at === ti ? run + 1 : 0;
    const wordStart = at === 0 || /[\s:(/-]/.test(t[at - 1]);
    score += 1 + run * 2 + (wordStart ? 3 : 0) - Math.min(3, (at - ti) * 0.1);
    ti = at + 1;
  }
  return score;
}
