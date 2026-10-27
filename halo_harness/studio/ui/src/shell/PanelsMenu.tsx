// The header's "+" menu (3.3.2.0 R2: the expanded rail's PANELS list before):
// one row per panel of the current section, its word saying what a press does
// ("add" an optional panel that is not on the page, "bring back" a strip or a
// panel that is not up, "focus" an open one) with the strip / float badges;
// revealPanel does the work. A section may add its own group under the panels
// (routes/index.tsx `menu`; Orchestra: New run and its runs). A paged section
// (Setup) has no panels and draws no "+".
import { Menu, type MenuGroup, type MenuRow } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { layoutStore } from "../lib/workspace/persist";
import type { PanelLayout, PanelSpec } from "../lib/workspace/types";
import { useSections, type SectionDef } from "../routes";
import { revealPanel } from "./commands";

/** The row's word and badges for one panel, from where it is now. */
export function panelWord(p: PanelSpec, lay: PanelLayout | undefined, up: boolean): { word: string; badges: string[]; title: string } {
  if (!lay && p.optional) return { word: "add", badges: [], title: `Add ${p.title} to this section` };
  if (!lay) return { word: "bring back", badges: [], title: up ? `Bring ${p.title} back and focus it` : `Bring the panels up and focus ${p.title}` };
  if (lay.collapsed) return { word: "bring back", badges: ["strip"], title: `Open the ${p.title} strip and focus it (then Alt+arrows move it)` };
  return { word: "focus", badges: lay.floating ? ["float"] : [], title: `Focus ${p.title} (then Alt+arrows move it)` };
}

function SectionPanels({ def }: { def: SectionDef }) {
  const ls = useStore(layoutStore(def.id), (s) => s);
  const own = def.menu?.(); // a hook; this component is keyed by section, so the order of hooks holds
  const rows: MenuRow[] = def.panels.map((p) => {
    const w = panelWord(p, ls.layout?.[p.id], !!ls.layout);
    return { id: p.id, label: p.title, icon: "grid", ...w, testid: "panels-menu-item", data: { panel: p.id, word: w.word }, run: () => revealPanel(def, p) };
  });
  const groups: MenuGroup[] = [{ name: "PANELS", rows }, ...(own ? [own] : [])];
  const extra = own ? " and runs" : "";
  return (
    <Menu
      icon="plus"
      label={`${def.title} panels${extra}`}
      title={`Panels${extra}: add one, bring one back, or focus it`}
      testid="panels-add"
      menuTestid="panels-menu"
      groups={groups}
    />
  );
}

export function PanelsMenu() {
  const section = useStore(studio, (s) => s.section);
  const def = useSections().find((s) => s.id === section);
  if (!def || def.paged || (!def.panels.length && !def.menu)) return null;
  return <SectionPanels key={def.id} def={def} />;
}
