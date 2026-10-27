// An enum row's control (3.3.3.0 R2): the row's choices; picking one saves
// it. While the key is unset the first line says so (its default named when
// it has one), and picking that line again changes nothing.
export function Select({ id, value, choices, fallback, label, disabled, onSave }: {
  id?: string;
  value: unknown;
  choices: string[];
  fallback: unknown;
  label: string;
  disabled?: boolean;
  onSave: (v: string) => void;
}) {
  const unset = value === null || value === undefined;
  const shown = unset ? "" : String(value);
  return (
    <select id={id} className="st-select mono" value={shown} aria-label={label} disabled={disabled} data-testid="settings-select"
            onChange={(e) => e.target.value && onSave(e.target.value)}>
      {unset && <option value="">{fallback !== null && fallback !== undefined ? `${String(fallback)} (default)` : "unset (default)"}</option>}
      {choices.map((c) => (
        <option key={c} value={c}>
          {c}
        </option>
      ))}
      {!unset && !choices.includes(shown) && <option value={shown}>{shown} (not a choice)</option>}
    </select>
  );
}
