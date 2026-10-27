// The left rail. 3.3.2.0 R1: an icon rail, 56 px by default (`data-rail="icons"`
// on .app): the sections only (shell/RailSections.tsx), one icon each, and a
// chevron at its foot that expands it to 248 px (`data-rail="open"`,
// remembered as `halo.studio.rail`). Expanded, each section shows its title,
// and below them (until 3.3.2.0 R2 moves them to the header and the palette)
// this section's own block (Orchestra: the runs), its panels (click to bring
// one back and focus it; an optional one is added), the Fleet tree (every
// harness, session and agent with its status, and the answer for a session
// that waits on you) and the layout actions (Arrange, Reset layout). Focus
// (`data-focus="on"`) hides the whole rail. A paged section (Setup, 3.3.1.0
// R1) has no panel list and no layout actions.
import { Button, Icon, Kbd } from "../lib/ui";
import { studio, toast, toggleRail, useStore } from "../lib/store";
import { arrangeLayout, layoutStore, resetLayout } from "../lib/workspace/persist";
import { sectionDef } from "../routes";
import { revealPanel } from "./commands";
import { RailSections } from "./RailSections";
import { FleetRail } from "../routes/fleet/FleetRail";

function Panels() {
  const section = useStore(studio, (s) => s.section);
  const ls = useStore(layoutStore(section), (s) => s);
  const def = sectionDef(section);
  return (
    <nav className="rail-group" aria-label="Panels">
      <div className="rail-label mono">PANELS</div>
      {def.panels.map((p) => {
        const lay = ls.layout?.[p.id];
        return (
          <button
            key={p.id}
            className="rail-item"
            onClick={() => revealPanel(def, p)}
            title={lay ? "Bring it back and focus it (then Alt+arrows move it)" : "Add it to this section"}
          >
            <Icon name="grid" />
            <span className="rail-item-text">{p.title}</span>
            {lay?.collapsed && <span className="badge">strip</span>}
            {lay?.floating && <span className="badge">float</span>}
            {!lay && p.optional && <span className="badge">add</span>}
          </button>
        );
      })}
    </nav>
  );
}

function Layout() {
  const section = useStore(studio, (s) => s.section);
  const ls = useStore(layoutStore(section), (s) => s);
  const def = sectionDef(section);
  return (
    <section className="rail-group rail-foot" aria-label="Layout">
      <div className="rail-label mono">LAYOUT · {ls.custom ? "YOURS" : "DEFAULT"}</div>
      <p className="rail-note">
        Drag a title bar to move a panel (the others make room), an edge to resize it against its neighbour. <Kbd keys="Alt+Shift+Down" /> grows the focused one.
      </p>
      <div className="rail-actions">
        <Button
          size="sm"
          icon={<Icon name="grid" />}
          disabled={!ls.layout}
          title="Every open panel back in its default place and size (strips stay strips)"
          data-testid="layout-arrange"
          onClick={() => {
            arrangeLayout(section, def.panels);
            toast(`${def.title} panels arranged`, "done");
          }}
        >
          Arrange
        </Button>
        <Button
          size="sm"
          icon={<Icon name="reset" />}
          disabled={!ls.custom}
          data-testid="layout-reset"
          onClick={() => {
            resetLayout(section);
            toast(`${def.title} layout reset`, "done");
          }}
        >
          Reset layout
        </Button>
      </div>
    </section>
  );
}

export function Rail() {
  const section = useStore(studio, (s) => s.section);
  const open = useStore(studio, (s) => s.rail === "open");
  const def = sectionDef(section);
  return (
    <aside className="rail" aria-label="Rail" data-testid="rail">
      <RailSections />
      {open && (
        <div className="rail-more" data-testid="rail-more">
          {def.rail && <def.rail />}
          {!def.paged && <Panels />}
          <FleetRail />
          {!def.paged && <Layout />}
        </div>
      )}
      <button
        className="icon-btn rail-toggle"
        onClick={toggleRail}
        aria-expanded={open}
        aria-label={open ? "Collapse the rail" : "Expand the rail"}
        title={open ? "Collapse the rail to its icons" : "Expand the rail: section titles, this section's panels, the Fleet tree and the layout"}
        data-testid="rail-toggle"
      >
        <Icon name={open ? "chevron-left" : "chevron-right"} />
      </button>
    </aside>
  );
}
