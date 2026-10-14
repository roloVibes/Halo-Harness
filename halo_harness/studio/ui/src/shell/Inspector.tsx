// The Inspector: a panel's Settings depth, opened by the gear in its title
// bar. Face, strip, float, the exact grid position, a per-panel reset, then
// whatever settings the panel itself declares. Esc closes it.
import { Button, Field, Icon, Surface } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { defaultPanel, arrange } from "../lib/workspace/grid";
import { hidePanel, layoutStore, patchPanel, setLayout } from "../lib/workspace/persist";
import { ROW, type PanelLayout } from "../lib/workspace/types";
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

export function Inspector() {
  const ref = useStore(studio, (s) => s.inspector);
  const section = ref?.section ?? "orchestra";
  const ls = useStore(layoutStore(section), (s) => s);
  if (!ref) return null;
  const def = sectionDef(ref.section);
  const spec = def.panels.find((p) => p.id === ref.panel);
  const p = ls.layout?.[ref.panel];
  if (!spec || !p) return null;
  const close = () => studio.update(() => ({ inspector: null }));
  const patch = (next: Partial<PanelLayout>) => patchPanel(section, spec.id, next);
  const place = (next: Partial<PanelLayout>) => {
    const cur = layoutStore(section).get().layout;
    if (cur) setLayout(section, arrange({ ...cur, [spec.id]: { ...cur[spec.id], ...next } }, spec.id));
  };
  const Settings = spec.settings;
  return (
    <aside className="inspector" aria-label="Inspector">
      <Surface className="inspector-surface" motion="none">
        <header className="inspector-head">
          <div>
            <div className="rail-label mono">SETTINGS · {def.title.toUpperCase()}</div>
            <h2 className="inspector-title">{spec.title}</h2>
          </div>
          <button className="icon-btn" onClick={close} aria-label="Close" title="Close (Esc)">
            <Icon name="close" />
          </button>
        </header>

        {spec.detail && (
          <div className="segmented" role="group" aria-label="Face">
            {(["glance", "detail"] as const).map((f) => (
              <button key={f} className={p.face === f ? "on" : ""} aria-pressed={p.face === f} onClick={() => patch({ face: f })}>
                {f === "glance" ? "Glance" : "Expand"}
              </button>
            ))}
          </div>
        )}
        <div className="toggles">
          <label className="check">
            <input type="checkbox" checked={p.collapsed} onChange={(e) => patch({ collapsed: e.target.checked })} /> Collapse to a strip
          </label>
          <label className="check">
            <input type="checkbox" checked={p.floating} onChange={(e) => patch({ floating: e.target.checked })} /> Float over the grid
          </label>
        </div>

        {!p.floating && (
          <div className="grid-fields">
            <NumberField label="COLUMN" value={p.x} min={0} max={23} onChange={(x) => place({ x })} />
            <NumberField label="ROW" value={p.y} min={0} onChange={(y) => place({ y })} />
            <NumberField label="WIDTH" value={p.w} min={4} max={24} onChange={(w) => place({ w })} />
            <NumberField label="HEIGHT" value={p.h} min={8} onChange={(h) => place({ h })} />
          </div>
        )}
        <div className="inspector-note mono muted">
          {p.floating ? `${p.fw} x ${p.fh} px floating` : `${p.w}/24 columns, ${p.h * ROW} px tall`}
        </div>
        <Button
          size="sm"
          icon={<Icon name="reset" />}
          onClick={() => {
            const fill = Math.floor((document.querySelector(".workspace")?.clientHeight || 600) / ROW) - 3;
            place({ ...defaultPanel(spec, fill), z: p.z });
          }}
        >
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
