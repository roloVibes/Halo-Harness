// api.lib.theme (3.3.13.0 R2, extension API 1.2): the theme the shell draws in. `tokens()` is the palette's colour
// variables as they are on <html> right now (`--bg`, `--text`, `--accent`, ...: use `var(--accent)` in your CSS and
// it follows a theme change by itself; read the values only to draw on a canvas), `current()` the theme's name,
// `onChange(fn)` a callback when it changes. `css(text)` adds a stylesheet of the pack's own to the page (a
// constructed sheet, so the shell's CSP holds) and returns the function that takes it away again.
import { studio } from "../lib/store";

const NAMES = ["bg", "bg-2", "surface", "surface-2", "surface-glass", "line", "line-strong", "text", "muted", "faint",
  "accent", "accent-2", "accent-ink", "accent-soft", "ok", "ok-soft", "warn", "warn-soft", "bad", "bad-soft"];

export function tokens(): Record<string, string> {
  const css = getComputedStyle(document.documentElement);
  const out: Record<string, string> = {};
  for (const n of NAMES) {
    const v = css.getPropertyValue("--" + n).trim();
    if (v) out[n] = v;
  }
  return out;
}

export function current(): string {
  return studio.get().theme;
}

export function onChange(fn: (theme: string) => void): () => void {
  let last = studio.get().theme;
  return studio.subscribe(() => {
    const now = studio.get().theme;
    if (now !== last) fn((last = now));
  });
}

export function css(text: string): () => void {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(text);
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  return () => {
    document.adoptedStyleSheets = document.adoptedStyleSheets.filter((s) => s !== sheet);
  };
}
