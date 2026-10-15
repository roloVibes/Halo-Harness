// The left rail: this section's panels (click to bring one back and focus
// it; an optional one is added), the section's own block (Flow: the runs and
// the flows), the Fleet tree (every harness, session and agent with its
// status, and the answer for a session that waits on you), and the layout
// actions.
import { Button, Icon, Kbd } from "../lib/ui";
import { studio, toast, useStore } from "../lib/store";
import { layoutStore, resetLayout } from "../lib/workspace/persist";
import { sectionDef } from "../routes";
import { revealPanel } from "./commands";
import { FleetRail } from "../routes/fleet/FleetRail";

export function Rail() {
  const section = useStore(studio, (s) => s.section);
  const open = useStore(studio, (s) => s.railOpen);
  const ls = useStore(layoutStore(section), (s) => s);
  const def = sectionDef(section);
  if (!open) return null;
  return (
    <aside className="rail" aria-label="Rail">
      <div className="rail-head">
        <div className="rail-title">{def.title}</div>
        <div className="rail-sub">{def.blurb}</div>
      </div>

      {def.rail && <def.rail />}

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

      <FleetRail />

      <section className="rail-group rail-foot" aria-label="Layout">
        <div className="rail-label mono">LAYOUT · {ls.custom ? "YOURS" : "DEFAULT"}</div>
        <p className="rail-note">
          Drag a title bar to move a panel, its edges to resize. <Kbd keys="Alt+Shift+Down" /> grows the focused one.
        </p>
        <Button
          size="sm"
          icon={<Icon name="reset" />}
          disabled={!ls.custom}
          onClick={() => {
            resetLayout(section);
            toast(`${def.title} layout reset`, "done");
          }}
        >
          Reset layout
        </Button>
      </section>
    </aside>
  );
}
