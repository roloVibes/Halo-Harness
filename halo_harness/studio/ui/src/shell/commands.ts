// The palette's commands and its fuzzy matcher. Groups: Go to, Help,
// Orchestra, Flow, Media, View, Layout, Open. Each command may show a key (the
// same hint the menus show).
import { cycleTheme, goSection, openHelp, setTheme, studio, toast, toggleRail } from "../lib/store";
import { layoutStore, resetLayout, showPanel } from "../lib/workspace/persist";
import type { PanelSpec } from "../lib/workspace/types";
import { SECTIONS, sectionDef, type SectionDef } from "../routes";
import { token } from "../lib/api";
import { flowCommands, mediaCommands } from "../routes/flow/commands";
import { orchestraCommands } from "../routes/orchestra/commands";

export type Command = { id: string; group: string; label: string; kbd?: string; hint?: string; run: () => void };

/** Bring a panel back (or add an optional one) and focus it, bringing the section's workspace up first. */
export function revealPanel(def: SectionDef, p: PanelSpec): void {
  const go = () => showPanel(def.id, p, def.id === "design");
  def.enter?.();
  if (layoutStore(def.id).get().layout) go();
  else window.setTimeout(go, 120);
}

export function commands(): Command[] {
  const cur = sectionDef(studio.get().section);
  const out: Command[] = SECTIONS.map((s) => ({
    id: "go-" + s.id,
    group: "Go to",
    label: s.title,
    hint: s.blurb,
    kbd: s.kbd,
    run: () => goSection(s.id),
  }));
  for (const s of [cur, ...SECTIONS.filter((x) => x.id !== cur.id)]) {
    out.push({
      id: "help-" + s.id,
      group: "Help",
      label: `Help: how ${s.title} works`,
      hint: s.id === cur.id ? "the steps, the panels and the keys" : s.blurb,
      kbd: s.id === cur.id ? "?" : undefined,
      run: () => {
        goSection(s.id);
        openHelp(s.id);
      },
    });
  }
  out.push(
    { id: "theme-toggle", group: "View", label: "Toggle theme", hint: "dark, light, auto", run: cycleTheme },
    { id: "theme-dark", group: "View", label: "Theme: dark (holo)", run: () => setTheme("dark") },
    { id: "theme-light", group: "View", label: "Theme: light", run: () => setTheme("light") },
    { id: "theme-auto", group: "View", label: "Theme: follow the system", run: () => setTheme("auto") },
    { id: "rail", group: "View", label: "Show or hide the rail", run: toggleRail },
    {
      id: "reset-layout",
      group: "Layout",
      label: `Reset layout (${cur.title})`,
      hint: "back to the default panels",
      run: () => {
        resetLayout(cur.id);
        toast(`${cur.title} layout reset`, "done");
      },
    },
  );
  for (const p of cur.panels) {
    out.push({
      id: "panel-" + p.id,
      group: "Layout",
      label: `${p.optional ? "Show" : "Focus"} panel: ${p.title}`,
      hint: "Alt+arrows move it, Alt+Shift+arrows resize it",
      run: () => revealPanel(cur, p),
    });
  }
  out.push(...orchestraCommands(), ...flowCommands(), ...mediaCommands());
  out.push({
    id: "open-legacy",
    group: "Open",
    label: "Open the classic page in a new tab",
    hint: "/legacy/",
    run: () => window.open(`legacy/index.html#t=${token()}`, "_blank", "noopener"),
  });
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
