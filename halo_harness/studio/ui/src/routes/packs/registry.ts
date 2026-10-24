// What the shell takes from the packs registry (3.2.0.0 R3), built once per
// registry read: the packs' own sections (after the seven core sections,
// Alt+8 and Alt+9 in the registry's order; later ones have no key), the panels they
// add to each core section, the palette's actions (group "pack <id>") and a
// pack section's "How this works" copy. routes/index.tsx sections() merges
// them with the seven core sections, whose order and keys never change.
import type { Command } from "../../shell/commands";
import type { SectionDef } from "../index";
import type { SectionHelpCopy } from "../sectionHelp";
import type { PackSectionId } from "../../lib/store";
import { PackSectionLoading } from "./Loading";
import { runAction } from "./nav";
import { coreSpecs, sectionSpecs } from "./panels";
import type { PanelSpec } from "../../lib/workspace/types";
import type { Registry } from "./types";

const FIRST_KEY = 8; // 3.2.0.0 R6: Alt+7 is the Packs section (the Pack Manager)
const LAST_KEY = 9;

export type PackSectionDef = SectionDef & { pack: string; help: string };
type Built = { reg: Registry | null; sections: PackSectionDef[]; core: Record<string, PanelSpec[]> };
let built: Built = { reg: null, sections: [], core: {} };

function build(reg: Registry): Built {
  const sections: PackSectionDef[] = [];
  const core: Record<string, PanelSpec[]> = {};
  let key = FIRST_KEY;
  for (const p of reg.packs) {
    for (const s of p.sections) {
      const kbd = key <= LAST_KEY ? `Alt+${key++}` : "";
      sections.push({ id: s.id as PackSectionId, title: s.title, kbd, blurb: s.blurb, panels: sectionSpecs(s.panels), pack: p.id, help: s.help,
                      ...(reg.boot ? { view: PackSectionLoading } : {}) }); // 3.2.1.0 R1: the page's boot sections, before the registry
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

/** "How this works" for a pack's section: its help line, then one step per panel (its first help line). */
export function packHelp(def: SectionDef): SectionHelpCopy {
  const d = def as PackSectionDef;
  const what = d.help || `${def.title}: ${def.blurb}.`;
  return {
    what: `${what} A section of pack ${d.pack || "?"}: Studio draws it from the pack's pack.yaml, and it goes away when the pack is disabled.`,
    steps: def.panels.map((p) => [p.title, (p.help || "").split("\n")[0] || p.about || ""] as [string, string]),
    keys: KEYS,
    terms: [],
  };
}
