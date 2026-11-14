// The Inspector: a panel's settings, opened from its title line's ... menu
// (Settings); while it is open it follows the panel you click. What the
// panel is and how to use it (its `about` and `help`), then the face
// (Expanded / Compact), open or closed and (3.6.0.0 R0a) a drawer's width in px instead of grid cells, a per-panel
// reset, and whatever settings the panel itself declares. Esc closes it.
// 3.3.2.0 R1 "the inspector asks first": closed until something opens it (a
// panel's Settings, a Design artboard's knobs); its close button or Esc gives
// the width back to the stage; open or closed is remembered per browser
// (`halo.studio.inspector`, lib/store.ts) and the next selection opens it again.
import { Button, Field, Icon, Surface } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { setDrawerWidth } from "../lib/workspace/controller";
import { hidePanel, layoutStore, patchPanel, resetPanel } from "../lib/workspace/persist";
import { contentWOf, roleOf } from "../lib/workspace/rules";
import { DRAWER_MAX, DRAWER_MIN, type PanelLayout } from "../lib/workspace/types";
import { sectionDef } from "../routes";

function NumberField({ label, value, onChange, min, max }: { label: string; value: number; onChange: (n: number) => void; min: number; max?: number }) {
  return (
    <Field label={label}>
      {(id) => (
        <input
          id={id}
          className="input mono"
          type="number"
          value={value}
          min={min}
          max={max}
          onChange={(e) => {
            const n = parseInt(e.target.value, 10);
            if (!Number.isNaN(n)) onChange(n);
          }}
        />
      )}
    </Field>
  );
}

/** The column is open only while there is a panel to show (a remembered one waits for its section's layout). */
export function useInspecting(): boolean {
  const ref = useStore(studio, (s) => s.inspector);
  const has = useStore(layoutStore(ref?.section ?? "roles"), (s) => !!ref && !!s.layout?.[ref.panel]);
  return has && !!sectionDef(ref?.section ?? "roles").panels.some((p) => p.id === ref?.panel);
}

export function Inspector() {
  const ref = useStore(studio, (s) => s.inspector);
  const section = ref?.section ?? "roles";
  const ls = useStore(layoutStore(section), (s) => s);
  if (!ref) return null;
  const def = sectionDef(ref.section);
  const spec = def.panels.find((p) => p.id === ref.panel);
  const p = ls.layout?.[ref.panel];
  if (!spec || !p) return null;
  const close = () => studio.update(() => ({ inspector: null }));
  const patch = (next: Partial<PanelLayout>) => patchPanel(section, spec.id, next);
  const role = roleOf(spec);
  const width = p.width ?? contentWOf(spec);
  const Settings = spec.settings;
  return (
    <aside className="inspector" aria-label="Inspector" data-testid="inspector">
      <Surface className="inspector-surface" motion="none">
        <header className="inspector-head">
          <div>
            <div className="rail-label mono">SETTINGS · {def.title.toUpperCase()}</div>
            <h2 className="inspector-title">{spec.title}</h2>
          </div>
          <button className="icon-btn" onClick={close} aria-label="Close" title="Close: the stage takes the width back (Esc)" data-testid="inspector-close">
            <Icon name="close" />
          </button>
        </header>
        {spec.about && <p className="inspector-about">{spec.about}</p>}
        {spec.help && (
          <ul className="inspector-help">
            {spec.help.split("\n").map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        )}

        {spec.detail && (
          <div className="segmented" role="group" aria-label="Face">
            {(["detail", "glance"] as const).map((f) => (
              <button key={f} className={p.face === f ? "on" : ""} aria-pressed={p.face === f} onClick={() => patch({ face: f })}>
                {f === "glance" ? "Compact" : "Expanded"}
              </button>
            ))}
          </div>
        )}
        {role !== "main" && (
          <div className="toggles">
            <label className="check">
              <input type="checkbox" checked={!p.collapsed} onChange={(e) => patch({ collapsed: !e.target.checked })} /> {role === "tab" ? "Shown in the main place" : "Open beside the main thing"}
            </label>
          </div>
        )}
        {role === "drawer" && (
          <div className="grid-fields">
            <NumberField label="WIDTH (PX)" value={width} min={DRAWER_MIN} max={DRAWER_MAX} onChange={(w) => setDrawerWidth(section, spec.id, w)} />
          </div>
        )}
        <div className="inspector-note mono muted">
          {role === "main" ? "the main thing of this view" : role === "tab" ? "a tab of the main thing" : `a ${spec.side === "left" ? "left" : "right"} drawer, ${width} px${p.width ? " (yours)" : " (its content's)"}`}
        </div>
        <Button size="sm" icon={<Icon name="reset" />} onClick={() => resetPanel(section, spec)}>
          Reset this panel
        </Button>
        {spec.optional && (
          <Button size="sm" variant="ghost" icon={<Icon name="close" />} onClick={() => (hidePanel(section, spec.id), close())}>
            Remove from {def.title}
          </Button>
        )}

        {Settings && (
          <section className="inspector-own">
            <div className="rail-label mono">THIS PANEL</div>
            <Settings />
          </section>
        )}
      </Surface>
    </aside>
  );
}
