// The header's overflow menu and the layout badge (3.3.2.0 R2: the expanded
// rail's LAYOUT block before). The "..." holds Arrange panels (`layout-arrange`),
// Reset layout (`layout-reset`) and How panels move (the section help's
// "Moving panels" part); a row with nothing to do stays in the list, disabled,
// its word saying why. The badge "custom layout" shows only while the
// section's layout is the user's own (`ls.custom`). A paged section (Setup)
// has no layout: neither draws.
import { Menu, type MenuRow } from "../lib/ui";
import { openHelp, studio, useStore } from "../lib/store";
import { layoutStore } from "../lib/workspace/persist";
import { sectionDef, type SectionDef } from "../routes";
import { arrangeSection, resetSection } from "./commands";

function More({ def }: { def: SectionDef }) {
  const ls = useStore(layoutStore(def.id), (s) => s);
  const rows: MenuRow[] = [
    {
      id: "arrange", label: "Arrange panels", icon: "grid", testid: "layout-arrange", disabled: !ls.layout,
      word: ls.layout ? "" : "not up yet",
      title: "Every open panel back in its default place and size (strips stay strips, a floating one floats)",
      run: () => arrangeSection(def),
    },
    {
      id: "reset", label: "Reset layout", icon: "reset", testid: "layout-reset", disabled: !ls.custom,
      word: ls.custom ? "" : "already default",
      title: "Forget your arrangement of this section: its default panels come back",
      run: () => resetSection(def),
    },
    { id: "moving", label: "How panels move", icon: "help", testid: "layout-help", title: "Drag, resize and the keys: the Moving panels part of this section's help", run: () => openHelp(def.id, "moving") },
  ];
  return <Menu icon="more" label={`${def.title}: layout`} title="More: arrange the panels, reset the layout, how panels move" testid="section-more" menuTestid="section-more-menu" groups={[{ name: "LAYOUT", rows }]} width={260} />;
}

function Badge({ def }: { def: SectionDef }) {
  const custom = useStore(layoutStore(def.id), (s) => s.custom);
  if (!custom) return null;
  return (
    <span className="badge layout-badge mono" data-testid="layout-badge" title={`${def.title}'s layout is yours, kept in this browser; the ... menu's Reset layout brings the default back`}>
      custom layout
    </span>
  );
}

export function SectionMore() {
  const section = useStore(studio, (s) => s.section);
  const def = sectionDef(section);
  if (def.paged) return null;
  return (
    <>
      <More key={def.id} def={def} />
      <Badge key={"b-" + def.id} def={def} />
    </>
  );
}
