// A labelled form row: the label (mono, small caps), the control, a hint or an error. 3.3.15.0 L1, the Instrument
// look: the control sits in `.field-control`, which draws a leading `›` in faint before a text input (the accent
// while it has the focus); an invalid row's control takes a `bad` border and its one line under it.
import { useId, type ReactNode } from "react";
export function Field({ label, hint, error, children }: { label: string; hint?: ReactNode; error?: string; children: (id: string) => ReactNode }) {
  const id = useId();
  return (
    <div className={"field" + (error ? " field-bad" : "")}>
      <label className="field-label mono" htmlFor={id}>
        {label}
      </label>
      <div className="field-control">{children(id)}</div>
      {error ? <div className="field-error">{error}</div> : hint ? <div className="field-hint">{hint}</div> : null}
    </div>
  );
}
