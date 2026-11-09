// The one text box (3.3.15.0 R3; the owner, 2026-11-09: "all boxes that have text in them need to be bigger"). A
// textarea at least three lines tall that grows with its text up to `maxRows` lines (12 by default) and then scrolls;
// no resize handle; the Instrument Field look (styles/textbox.css: the hairline, the accent border on focus, prose
// 13 px for text, mono 12 px for a data box with `mono`). It grows by CSS `field-sizing: content` where the browser
// has it, else by its measured scrollHeight on every change. `fill` makes it take the free height of its container
// (the Prompt panel's composer): a hidden mirror of the text sizes a wrapper (three lines at the least, `maxRows` at
// the most), the parent stretches the wrapper into its free height and the textarea fills the wrapper. Every other
// prop (value, onChange, onKeyDown, placeholder, data-testid, ref, ...) goes to the textarea. `ui/src` holds no other
// `<textarea` (tests/test_studio_textboxes.py pins it).
import { useCallback, useLayoutEffect, useRef, type CSSProperties, type Ref, type TextareaHTMLAttributes } from "react";

export type TextBoxProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "rows"> & {
  ref?: Ref<HTMLTextAreaElement>;
  /** The most lines it grows to before it scrolls (12). */
  maxRows?: number;
  /** A data box (YAML, JSON, a list, a turn typed as in the terminal): mono 12 px. Text is prose 13 px. */
  mono?: boolean;
  /** Take the free height of the container (a flex or grid parent that stretches it). */
  fill?: boolean;
};

const SIZES_ITSELF = typeof CSS !== "undefined" && typeof CSS.supports === "function" && CSS.supports("field-sizing", "content");

function assign<T>(ref: Ref<T> | undefined, el: T | null): void {
  if (typeof ref === "function") ref(el);
  else if (ref && typeof ref === "object") (ref as { current: T | null }).current = el;
}

export function TextBox({ ref, maxRows = 12, mono, fill, className, style, value, onInput, ...rest }: TextBoxProps) {
  const own = useRef<HTMLTextAreaElement | null>(null);
  const attach = useCallback((el: HTMLTextAreaElement | null) => {
    own.current = el;
    assign(ref, el);
  }, [ref]);
  // The fallback: no field-sizing, so the box is as tall as its text (min-height and max-height in CSS clamp it).
  const grow = useCallback(() => {
    const el = own.current;
    if (!el || fill || SIZES_ITSELF) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`;
  }, [fill]);
  useLayoutEffect(grow, [grow, value]);
  const rows = { "--tb-max": String(maxRows) } as CSSProperties;
  const box = (
    <textarea {...rest} ref={attach} rows={3} value={value} className={`input textbox${mono ? " mono" : ""}${className ? ` ${className}` : ""}`}
              style={{ ...style, ...rows }} data-fill={fill || undefined} onInput={(e) => (grow(), onInput?.(e))} />
  );
  if (!fill) return box;
  return (
    <div className={`textbox-fill${mono ? " mono" : ""}`} style={rows} data-mirror={`${value ?? ""} `}>
      {box}
    </div>
  );
}
