// The left rail: this section's panels (click to bring one back and focus
// it; an optional one is added), the section's own block (Orchestra: the
// runs), the Fleet tree (every harness, session and agent with its
// status, and the answer for a session that waits on you), and the layout
// actions (3.2.2.0 R5: Arrange beside Reset layout). 3.2.0.0 R3: the packs'
// sections, under a thin "packs" divider. 3.3.1.0 R1: a paged section (Setup) has no panel list and no layout actions.
import { Button, Icon, Kbd } from "../lib/ui";
import { studio, toast, useStore } from "../lib/store";
import { arrangeLayout, layoutStore, resetLayout } from "../lib/workspace/persist";
import { goSection } from "../lib/store";
import { sectionDef, useSections } from "../routes";
import { revealPanel } from "./commands";
import { FleetRail } from "../routes/fleet/FleetRail";

export function Rail() {
  const section = useStore(studio, (s) => s.section);
  const open = useStore(studio, (s) => s.railOpen);
  const ls = useStore(layoutStore(section), (s) => s);
  const def = sectionDef(section);
  const packSections = useSections().filter((s) => s.id.includes("--"));
  if (!open) return null;
  return (
    <aside className="rail" aria-label="Rail">
      <div className="rail-head">
        <div className="rail-title">{def.title}</div>
        <div className="rail-sub">{def.blurb}</div>
      </div>

      {def.rail && <def.rail />}

      {!def.paged && (
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
      )}

      {packSections.length > 0 && (
        <nav className="rail-group rail-packs" aria-label="Packs" data-testid="rail-packs">
          <div className="rail-label mono rail-divider">PACKS</div>
          {packSections.map((s) => (
            <button key={s.id} className={"rail-item" + (s.id === section ? " on" : "")} onClick={() => goSection(s.id)} title={s.blurb} data-testid="rail-pack-section">
              <Icon name="diamond" />
              <span className="rail-item-text">{s.title}</span>
              {s.kbd && <Kbd keys={s.kbd} />}
            </button>
          ))}
        </nav>
      )}

      <FleetRail />

      {!def.paged && (
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
      )}
    </aside>
  );
}
