// A labelled form row: the label (mono, small caps), the control, a hint or an error.
import { useId, type ReactNode } from "react";

export function Field({ label, hint, error, children }: { label: string; hint?: ReactNode; error?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className={"field" + (error ? " field-bad" : "")}>
      <label className="field-label mono" htmlFor={id}>
        {label}
      </label>
      {children(id)}
      {error ? <div className="field-error">{error}</div> : hint ? <div className="field-hint">{hint}</div> : null}
    </div>
  );
}
