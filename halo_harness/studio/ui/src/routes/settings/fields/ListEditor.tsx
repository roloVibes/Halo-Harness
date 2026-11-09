// A list row's control (3.3.3.0 R2): one item per line; a line that reads as
// JSON (11434, true, {"name": ...}) is that value, any other line a string.
// Save writes the list (an empty box writes []); Ctrl+Enter saves too. 3.3.15.0 R3: the box is the one TextBox.
import { useEffect, useState } from "react";
import { Button, TextBox } from "../../../lib/ui";

export function toLines(value: unknown): string {
  if (!Array.isArray(value)) return "";
  return value.map((v) => (typeof v === "string" ? v : JSON.stringify(v))).join("\n");
}

export function fromLines(text: string): unknown[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return l;
      }
    });
}

export function ListEditor({ id, value, fallback, label, disabled, onSave }: {
  id?: string;
  value: unknown;
  fallback: unknown;
  label: string;
  disabled?: boolean;
  onSave: (v: unknown[]) => void;
}) {
  const saved = toLines(value);
  const [text, setText] = useState(saved);
  useEffect(() => {
    setText(saved);
  }, [saved]);
  const changed = text.trim() !== saved.trim();
  const shownDefault = Array.isArray(fallback) && fallback.length ? toLines(fallback).split("\n").join(", ") : "";
  return (
    <div className="st-list">
      <TextBox id={id} mono className="st-area" value={text}
               aria-label={label} spellCheck={false} disabled={disabled} data-testid="settings-list"
               placeholder={shownDefault && shownDefault.length <= 28 ? `one per line (default: ${shownDefault})` : "one per line"} onChange={(e) => setText(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) (e.preventDefault(), onSave(fromLines(text)));
               }} />
      <Button size="sm" disabled={disabled || !changed} onClick={() => onSave(fromLines(text))} data-testid="settings-list-save">
        Save
      </Button>
    </div>
  );
}
