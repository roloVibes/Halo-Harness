// A bool row's control (3.3.3.0 R2): a switch that saves on the click. A
// value that is a mapping (models.learn may hold its knobs) is on unless it
// says `enabled: false`.
export function isOn(value: unknown): boolean {
  if (value && typeof value === "object" && !Array.isArray(value)) return (value as Record<string, unknown>).enabled !== false;
  return value === true;
}

export function Toggle({ id, value, label, disabled, onSave }: { id?: string; value: unknown; label: string; disabled?: boolean; onSave: (v: boolean) => void }) {
  const on = isOn(value);
  return (
    <button type="button" id={id} role="switch" aria-checked={on} aria-label={label} className={"st-toggle" + (on ? " on" : "")}
            disabled={disabled} onClick={() => onSave(!on)} data-testid="settings-toggle" data-on={on}>
      <span className="st-toggle-knob" aria-hidden="true" />
      <span className="st-toggle-word mono">{on ? "on" : "off"}</span>
    </button>
  );
}
