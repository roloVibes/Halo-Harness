// The left rail: this section's panels (click to bring one back and focus
// it), the live sessions the feed is attached to, and the layout actions.
import { Button, Empty, Icon, Kbd } from "../lib/ui";
import { studio, toast, useStore } from "../lib/store";
import { focusPanel, layoutStore, patchPanel, resetLayout } from "../lib/workspace/persist";
import { sectionDef } from "../routes";

export function Rail() {
  const section = useStore(studio, (s) => s.section);
  const open = useStore(studio, (s) => s.railOpen);
  const sessions = useStore(studio, (s) => s.feed.sessions);
  const ls = useStore(layoutStore(section), (s) => s);
  const def = sectionDef(section);
  if (!open) return null;
  return (
    <aside className="rail" aria-label="Rail">
      <div className="rail-head">
        <div className="rail-title">{def.title}</div>
        <div className="rail-sub">{def.blurb}</div>
      </div>

      <nav className="rail-group" aria-label="Panels">
        <div className="rail-label mono">PANELS</div>
        {def.panels.map((p) => {
          const lay = ls.layout?.[p.id];
          return (
            <button
              key={p.id}
              className="rail-item"
              onClick={() => {
                patchPanel(section, p.id, { collapsed: false }, false);
                focusPanel(section, p.id);
              }}
              title="Bring it back and focus it (then Alt+arrows move it)"
            >
              <Icon name="grid" />
              <span className="rail-item-text">{p.title}</span>
              {lay?.collapsed && <span className="badge">strip</span>}
              {lay?.floating && <span className="badge">float</span>}
            </button>
          );
        })}
      </nav>

      <section className="rail-group" aria-label="Live sessions">
        <div className="rail-label mono">LIVE SESSIONS · {sessions.length}</div>
        {sessions.length ? (
          sessions.map((s) => (
            <div key={s.session_id} className="rail-session">
              <span className="rail-session-dot" aria-hidden="true" />
              <span className="rail-item-text">{s.title || s.session_id.slice(0, 8)}</span>
              <span className="mono muted">{s.mode || "default"}</span>
            </div>
          ))
        ) : (
          <Empty title="None yet" body="Run halo in a terminal: it shows up here." />
        )}
      </section>

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
