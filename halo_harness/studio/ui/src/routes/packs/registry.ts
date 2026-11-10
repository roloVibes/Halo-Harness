// What the shell takes from the packs registry (3.2.0.0 R3), built once per
// registry read: the packs' own sections (after the seven core sections, 3.3.16.0 R1;
// the pack's own sections take Alt+8, Alt+9 and Alt+0 in turn,
// the rest are reached by their rail row or the palette), the panels they
// add to each core section, the palette's actions (group "pack <id>") and a
// pack section's "How this works" copy. routes/index.tsx sections() merges
// them with the core sections, whose order and keys never change. 3.3.13.0 R2: a section with a `view` is drawn whole
// by the pack's own module (PackView.tsx): no panel grid, no "+" menu (`paged`).
import type { Command } from "../../shell/commands";
import type { SectionDef } from "../index";
import type { SectionHelpCopy } from "../sectionHelp";
import type { PackSectionId } from "../../lib/store";
import { PackSectionLoading } from "./Loading";
import { runAction } from "./nav";
import { coreSpecs, sectionSpecs } from "./panels";
import { PackView } from "./PackView";
import type { PanelSpec } from "../../lib/workspace/types";
import type { Registry } from "./types";

// 3.3.16.0 R1: Agents took in Team, Roles and Orchestra, Local is the last core section;
// the eighth, ninth and tenth slots are the pack's own sections (the design pack's, when it is the first: Alt+8).
const FIRST_KEY = 8;
const LAST_KEY = 10;
const keyOf = (n: number) => `Alt+${n % 10}`;

export type PackSectionDef = SectionDef & { pack: string; help: string };
type Built = { reg: Registry | null; sections: PackSectionDef[]; core: Record<string, PanelSpec[]> };
let built: Built = { reg: null, sections: [], core: {} };

function build(reg: Registry): Built {
  const sections: PackSectionDef[] = [];
  const core: Record<string, PanelSpec[]> = {};
  let key = FIRST_KEY;
  for (const p of reg.packs) {
    for (const s of p.sections) {
      const kbd = key <= LAST_KEY ? keyOf(key++) : "";
      const page = s.view ? { view: PackView, paged: true } : {}; // 3.3.13.0 R2: the pack's own module draws the page
      sections.push({ id: s.id as PackSectionId, title: s.title, kbd, blurb: s.blurb, panels: sectionSpecs(s.panels), pack: p.id, help: s.help,
                      ...page, ...(reg.boot ? { view: PackSectionLoading } : {}) }); // 3.2.1.0 R1: the page's boot sections, before the registry
    }
    for (const x of p.panels) (core[x.section] ||= []).push(...coreSpecs([x]));
  }
  return { reg, sections, core };
}

function current(reg: Registry): Built {
  if (built.reg !== reg) built = build(reg);
  return built;
}

export function packSections(reg: Registry): PackSectionDef[] {
  return current(reg).sections;
}

/** The panels the packs add to core section `id` (they sit under its own, as strips). */
export function packPanels(reg: Registry, id: string): PanelSpec[] {
  return current(reg).core[id] || [];
}

/** The palette's pack actions, in the registry's order. */
export function packCommands(reg: Registry): Command[] {
  return reg.packs.flatMap((p) =>
    p.palette.map((e) => ({ id: "pack-" + e.id, group: e.group, label: e.label, hint: `from pack ${p.id}`, run: () => runAction(e.action) })),
  );
}

/** The palette's pack groups, after the sections' own groups. */
export function packGroups(reg: Registry): string[] {
  return reg.packs.filter((p) => p.palette.length).map((p) => `pack ${p.id}`);
}

const KEYS: [string, string][] = [
  ["?", "help for the focused panel; press it again (or away from a panel) for this page"],
  ["Alt+Arrows", "move the focused panel; Alt+Shift+Arrows resizes it"],
  ["Mod+K", "every command, with its key"],
];

/** "How this works" for a pack's section: its help's first line, then one step per panel (its first help line); a
 *  section the pack draws itself (3.3.13.0 R2, a view) takes its steps from its help's other lines, "Step: what". */
export function packHelp(def: SectionDef): SectionHelpCopy {
  const d = def as PackSectionDef;
  const [first, ...rest] = (d.help || "").split("\n").map((l) => l.trim()).filter(Boolean);
  const what = first || `${def.title}: ${def.blurb}.`;
  const own = rest.map((l) => (l.includes(": ") ? (l.split(/: (.*)/s, 2) as [string, string]) : (["", l] as [string, string])));
  return {
    what: `${what} A section of pack ${d.pack || "?"}: Studio draws it from the pack's pack.yaml, and it goes away when the pack is disabled.`,
    steps: def.view && def.paged ? own : def.panels.map((p) => [p.title, (p.help || "").split("\n")[0] || p.about || ""] as [string, string]),
    keys: KEYS,
    terms: [],
  };
}
