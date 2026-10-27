// The left rail: the sections only. 3.3.2.0 R1: an icon rail, 56 px by
// default (`data-rail="icons"` on .app), one icon per section
// (shell/RailSections.tsx), and a chevron at its foot that expands it to show
// the section titles (`data-rail="open"`, remembered as `halo.studio.rail`).
// 3.3.2.0 R2: nothing else, expanded or not: the panels are the header's "+"
// menu, Arrange and Reset layout its "..." menu and the palette, Orchestra's
// runs a group in its "+" menu, and the Fleet tree (its inline answers and the
// "While you were away" card) the Fleet section's Tree panel. Focus
// (`data-focus="on"`) hides the whole rail.
import { Icon } from "../lib/ui";
import { studio, toggleRail, useStore } from "../lib/store";
import { RailSections } from "./RailSections";

export function Rail() {
  const open = useStore(studio, (s) => s.rail === "open");
  return (
    <aside className="rail" aria-label="Rail" data-testid="rail">
      <RailSections />
      <button
        className="icon-btn rail-toggle"
        onClick={toggleRail}
        aria-expanded={open}
        aria-label={open ? "Collapse the rail" : "Expand the rail"}
        title={open ? "Collapse the rail to its icons" : "Expand the rail: the section titles beside their icons"}
        data-testid="rail-toggle"
      >
        <Icon name={open ? "chevron-left" : "chevron-right"} />
      </button>
    </aside>
  );
}
