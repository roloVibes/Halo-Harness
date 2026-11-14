// The header's overflow menu (3.3.2.0 R2; 3.6.0.0 R0a: Arrange and the "custom layout" badge went with the grid).
// The "..." holds Reset layout (`layout-reset`: every drawer closed, widths back to their content's) and How panels
// open (the section help's "Moving panels" part); Session adds Open the glance. A row with nothing to do stays in
// the list, disabled, its word saying why. A paged section (Setup) has no layout: it does not draw.
import { Menu, type MenuRow } from "../lib/ui";
import { openHelp, studio, useStore } from "../lib/store";
import { layoutStore } from "../lib/workspace/persist";
import { useSectionDef, type SectionDef } from "../routes";
import { layoutWords, resetSection } from "./commands";
import { GLANCE_HINT, openGlanceDoor } from "../routes/glance/Door";

function More({ def }: { def: SectionDef }) {
  useStore(layoutStore(def.id), (s) => s); // the words follow what is open
  const w = layoutWords(def);
  const rows: MenuRow[] = [
    {
      id: "reset", label: "Reset layout", icon: "reset", testid: "layout-reset", disabled: !!w.reset,
      word: w.reset ? "already default" : "",
      title: "Every drawer of this view closed and back to its own width: the main thing has the room",
      run: () => resetSection(def),
    },
    { id: "moving", label: "How panels open", icon: "help", testid: "layout-help", title: "The view bar, drawers and tabs: the Moving panels part of this section's help", run: () => openHelp(studio.get().section, "moving") },
  ];
  const elsewhere: MenuRow[] = [{ id: "glance", label: "Open the glance", icon: "popout", testid: "session-glance", title: GLANCE_HINT, run: openGlanceDoor }]; // 3.4.1.0 R4
  const groups = def.id === "session" ? [{ name: "LAYOUT", rows }, { name: "ELSEWHERE", rows: elsewhere }] : [{ name: "LAYOUT", rows }];
  return <Menu icon="more" label={`${def.title}: layout`} title="More: reset the layout, how panels open" testid="section-more" menuTestid="section-more-menu" groups={groups} width={260} />;
}

export function SectionMore() {
  const section = useStore(studio, (s) => s.section);
  const def = useSectionDef(section); // 3.3.16.0 R1: Agents' follows its view
  if (def.paged) return null;
  return <More key={def.id} def={def} />;
}
