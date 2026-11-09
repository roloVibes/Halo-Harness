// A mapping row's control, and a keyed row's whole section (3.3.3.0 R2): the
// JSON as text. Save (or Ctrl+Enter) sends the text as typed; the server
// parses it and checks its shape, and a refusal's problems show under the box
// (config.json is left as it was). 3.3.15.0 R3: the box is the one TextBox (grows with the JSON to 12 lines).
import { useEffect, useState } from "react";
import { Button, TextBox } from "../../../lib/ui";

export function pretty(value: unknown): string {
  return value === null || value === undefined ? "" : JSON.stringify(value, null, 2);
}

export function JsonEditor({ id, value, label, problems, disabled, testid = "settings-json", onSave }: {
  id?: string;
  value: unknown;
  label: string;
  problems?: string[];
  disabled?: boolean;
  testid?: string;
  onSave: (text: string) => void;
}) {
  const saved = pretty(value);
  const [text, setText] = useState(saved);
  useEffect(() => {
    setText(saved);
  }, [saved]);
  const changed = text.trim() !== saved.trim() && !!text.trim();
  return (
    <div className="st-json">
      <TextBox id={id} mono className="st-area" value={text}
               aria-label={label} spellCheck={false} disabled={disabled} data-testid={testid} placeholder="{ }"
               onChange={(e) => setText(e.target.value)}
               onKeyDown={(e) => {
                 if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && changed) (e.preventDefault(), onSave(text));
               }} />
      <div className="st-json-foot">
        <Button size="sm" disabled={disabled || !changed} onClick={() => onSave(text)} data-testid={`${testid}-save`}>
          Save
        </Button>
        {problems && problems.length > 0 && (
          <ul className="st-problems" data-testid="settings-problems" role="alert">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
