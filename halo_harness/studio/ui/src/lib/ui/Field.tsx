// A labelled form row: the label (mono, small caps), the control, a hint or an error. 3.3.15.0 L1, the Instrument
// look: the control sits in `.field-control`, which draws a leading `›` in faint before a text input (the accent
// while it has the focus); an invalid row's control takes a `bad` border and its one line under it.
// 3.3.15.0 R3: `multiline` makes the control the one text box (TextBox.tsx: three lines at the least, grows with its
// text) with those props, the label pointing at it; otherwise `children(id)` draws the control.
import { useId, type ReactNode } from "react";
import { TextBox, type TextBoxProps } from "./TextBox";

export function Field({ label, hint, error, multiline, children }: {
  label: string;
  hint?: ReactNode;
  error?: string;
  multiline?: TextBoxProps;
  children?: (id: string) => ReactNode;
}) {
  const id = useId();
  return (
    <div className={"field" + (error ? " field-bad" : "")}>
      <label className="field-label mono" htmlFor={id}>
        {label}
      </label>
      <div className="field-control">{multiline ? <TextBox id={id} {...multiline} /> : children?.(id)}</div>
      {error ? <div className="field-error">{error}</div> : hint ? <div className="field-hint">{hint}</div> : null}
    </div>
  );
}
