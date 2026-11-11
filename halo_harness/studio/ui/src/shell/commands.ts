// The palette's commands and its fuzzy matcher. Groups: Go to, Help, then
// the sections in the registry's order (3.3.16.0 R1: Agents -- its views, then Cast's Roles lines and Runs'
// Orchestra lines -- and Fleet; Session has none of its own), Media, View, Layout. Each
// command may show a key (the same hint the menus show; 3.3.2.0 R1: the Go to
// entries carry each section's Alt+N, which the icon rail no longer prints; 3.3.2.0 R2: Layout's
// "Arrange panels" and "Reset layout" name the section in the hint). 3.2.0.0 R3: the packs' sections join Go to and
// Help, and each pack's palette actions come last in their own group ("pack <id>").
import { goSection, openHelp, studio, toast, toggleFocus, toggleRail } from "../lib/store";
import { themeCommands } from "./themeCommands"; // 3.3.12.0 R1
import { openGlossary } from "../lib/glossary";
import { setDensity } from "../lib/density";
import { arrangeLayout, layoutStore, resetLayout, showPanel, whenLaidOut } from "../lib/workspace/persist";
import type { PanelSpec } from "../lib/workspace/types";
import { sectionDef, sections, type SectionDef } from "../routes";
import { packCommands } from "../routes/packs/registry";
import { packs } from "../routes/packs/store";
import { mediaCommands } from "../routes/media/commands";
import { orchestraCommands } from "../routes/orchestra/commands";
import { fleetCommands } from "../routes/fleet/commands";
import { packPageCommands } from "../packlib/kbd"; // 3.3.13.0 R2: a pack page's own lines (api.lib.commands)
import { rolesCommands } from "../routes/roles/commands";
import { agentsCommands } from "../routes/agents/commands";
import { settingsCommands } from "../routes/settings/commands";
import { localCommands } from "../routes/local/commands";
import { promptCommand } from "../routes/session/promptStore";

/** `disabled`: drawn with its hint saying why (3.3.2.0 R2: nothing to arrange, nothing to reset); Enter does nothing. */
export type Command = { id: string; group: string; label: string; kbd?: string; hint?: string; disabled?: boolean; run: () => void };

/** Bring a panel back (or add an optional one) and focus it, bringing the section's workspace up first. */
export function revealPanel(def: SectionDef, p: PanelSpec): void {
  const go = () => showPanel(def.id, p, !!def.paged); // 3.3.13.0 R2: over a paged section's page (Local: Media) it floats
  def.enter?.();
  whenLaidOut(def.id, go); // the section may still be mounting (one 120 ms retry dropped the panel on a slow runner)
}

/** 3.3.2.0 R2: what Arrange and Reset layout would say when there is nothing to do ("" when there is). */
export function layoutWords(def: SectionDef): { arrange: string; reset: string } {
  const ls = layoutStore(def.id).get();
  return {
    arrange: ls.layout ? "" : `${def.title}: nothing to arrange, its panels are not up`,
    reset: ls.custom ? "" : `${def.title}: nothing to reset, the layout is the default`,
  };
}

/** Arrange (the palette and the header's ... menu): the open panels back in their default places. */
export function arrangeSection(def: SectionDef): void {
  arrangeLayout(def.id, def.panels);
  toast(`${def.title} panels arranged`, "done");
}

/** Reset layout (the palette and the header's ... menu): forget the user's arrangement. */
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
  const here = studio.get().section; // 3.3.16.0 R1: Agents' def is the part it draws now (its id roles or orchestra)
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
    { id: "focus", group: "View", label: "Focus", hint: "hide the rail, the inspector and the status bar; again brings them back", kbd: "F", run: toggleFocus },
  );
  if (!cur.paged) { // 3.3.1.0 R1: a paged section (Setup) has no layout to reset or arrange
    const w = layoutWords(cur); // 3.3.2.0 R2: the section's title in the hint; the words say when there is nothing to do
    out.push(
      { id: "arrange-layout", group: "Layout", label: "Arrange panels", hint: w.arrange || `${cur.title}: the open panels back in their default places and sizes`, disabled: !!w.arrange, run: () => arrangeSection(cur) },
      { id: "reset-layout", group: "Layout", label: "Reset layout", hint: w.reset || `${cur.title}: back to the default panels`, disabled: !!w.reset, run: () => resetSection(cur) },
    );
  }
  for (const p of cur.panels) {
    out.push({
      id: "panel-" + p.id,
      group: "Layout",
      label: `${p.optional ? "Show" : "Focus"} panel: ${p.title}`,
      hint: "Alt+arrows move it, Alt+Shift+arrows resize it",
      run: () => revealPanel(cur, p),
    });
  }
  out.push(promptCommand()); // 3.3.11.0 R1: Session's Prompt panel, Alt+Enter
  out.push(...agentsCommands(), ...rolesCommands(), ...orchestraCommands(), ...fleetCommands(), ...mediaCommands());
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
