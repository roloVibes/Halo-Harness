// Small form controls for the Roles editors (3.0.7.0 R2). A text, number or
// list box keeps what you type locally and commits it on Enter or when it
// loses the focus, so one edit is one step in the undo history (not one per
// key). A list is comma separated. Labels are the shell's mono field labels.
import { useEffect, useId, useState, type ReactNode } from "react";

type Base = { label?: string; hint?: ReactNode; testid?: string; placeholder?: string; disabled?: boolean };

export function Row({ label, hint, children, id }: { label?: string; hint?: ReactNode; children: ReactNode; id?: string }) {
  return (
    <div className="field re-field">
      {label && <label className="field-label mono" htmlFor={id}>{label}</label>}
      {children}
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  );
}

function useDraft(value: string): [string, (v: string) => void] {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return [draft, setDraft];
}

export function TextIn({ value, onCommit, label, hint, testid, placeholder, disabled, area }: Base & { value: string; onCommit: (v: string) => void; area?: boolean }) {
  const id = useId();
  const [draft, setDraft] = useDraft(value);
  const commit = () => draft !== value && onCommit(draft);
  const props = {
    id, className: "input", value: draft, placeholder, disabled, "data-testid": testid,
    onChange: (e: { target: { value: string } }) => setDraft(e.target.value),
    onBlur: commit,
  };
  return (
    <Row label={label} hint={hint} id={id}>
      {area ? (
        <textarea {...props} rows={3} />
      ) : (
        <input {...props} onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), commit())} />
      )}
    </Row>
  );
}

export function NumberIn({ value, onCommit, label, hint, testid, placeholder }: Base & { value: number | undefined; onCommit: (v: number | undefined) => void }) {
  return (
    <TextIn label={label} hint={hint} testid={testid} placeholder={placeholder} value={value === undefined || value === null ? "" : String(value)}
            onCommit={(v) => onCommit(v.trim() === "" ? undefined : Number(v))} />
  );
}

export function ListIn({ value, onCommit, label, hint, testid, placeholder }: Base & { value: string[]; onCommit: (v: string[]) => void }) {
  return (
    <TextIn label={label} hint={hint ?? "comma separated"} testid={testid} placeholder={placeholder} value={(value || []).join(", ")}
            onCommit={(v) => onCommit(v.split(",").map((s) => s.trim()).filter(Boolean))} />
  );
}

export function Check({ value, onChange, label, testid }: { value: boolean; onChange: (v: boolean) => void; label: string; testid?: string }) {
  return (
    <label className="check re-check">
      <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} data-testid={testid} /> {label}
    </label>
  );
}

export function Pick({ value, options, onChange, label, hint, testid, labels }: Base & { value: string; options: string[]; onChange: (v: string) => void; labels?: Record<string, string> }) {
  const id = useId();
  const opts = options.includes(value) ? options : [value, ...options];
  return (
    <Row label={label} hint={hint} id={id}>
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}>
        {opts.map((o) => <option key={o} value={o}>{labels?.[o] ?? (o || "(none)")}</option>)}
      </select>
    </Row>
  );
}
