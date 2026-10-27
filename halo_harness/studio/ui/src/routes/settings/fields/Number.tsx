// An int or float row's control (3.3.3.0 R2): a number field that saves on
// Enter or when it loses focus, only when the text changed. Text that is not
// a number goes to the server as typed, so its problem line says why.
import { useEffect, useState } from "react";

export function NumberField({ id, value, fallback, float, label, disabled, onSave }: {
  id?: string;
  value: unknown;
  fallback: unknown;
  float?: boolean;
  label: string;
  disabled?: boolean;
  onSave: (v: unknown) => void;
}) {
  const saved = value === null || value === undefined ? "" : String(value);
  const [text, setText] = useState(saved);
  useEffect(() => {
    setText(saved);
  }, [saved]);
  const commit = () => {
    const t = text.trim();
    if (t === saved || !t) return setText(saved);
    const n = Number(t);
    onSave(Number.isFinite(n) && (float || Number.isInteger(n)) ? n : t);
  };
  return (
    <input id={id} className="st-input st-number mono" type="text" inputMode={float ? "decimal" : "numeric"} value={text} aria-label={label}
           placeholder={fallback !== null && fallback !== undefined ? `${String(fallback)} (default)` : "unset (default)"}
           disabled={disabled} data-testid="settings-number" onChange={(e) => setText(e.target.value)} onBlur={commit}
           onKeyDown={(e) => {
             if (e.key === "Enter") (e.preventDefault(), commit());
             if (e.key === "Escape") setText(saved);
           }} />
  );
}
