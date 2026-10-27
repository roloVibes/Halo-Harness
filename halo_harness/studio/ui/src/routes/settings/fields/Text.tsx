// A string, model or path row's control (3.3.3.0 R2): a text field that saves
// on Enter or when it loses focus, only when the text changed. A secret row
// is a password field that never holds the saved value: it shows that one is
// set, and what you type replaces it.
import { useEffect, useState } from "react";

export function TextField({ id, value, fallback, secret, isSet, label, disabled, onSave }: {
  id?: string;
  value: unknown;
  fallback: unknown;
  secret?: boolean;
  isSet?: boolean;
  label: string;
  disabled?: boolean;
  onSave: (v: string) => void;
}) {
  const saved = secret || value === null || value === undefined ? "" : String(value);
  const [text, setText] = useState(saved);
  useEffect(() => {
    setText(saved);
  }, [saved]);
  const commit = () => {
    const t = text.trim();
    if (t === saved || !t) return setText(saved);
    onSave(t);
    if (secret) setText("");
  };
  const hint = secret && isSet ? "set, hidden: type to replace it" : fallback !== null && fallback !== undefined ? `${String(fallback)} (default)` : "unset (default)";
  return (
    <input id={id} className="st-input mono" type={secret ? "password" : "text"} value={text} aria-label={label} placeholder={hint}
           autoComplete="off" spellCheck={false} disabled={disabled} data-testid="settings-text" onChange={(e) => setText(e.target.value)}
           onBlur={commit} onKeyDown={(e) => {
             if (e.key === "Enter") (e.preventDefault(), commit());
             if (e.key === "Escape") setText(saved);
           }} />
  );
}
