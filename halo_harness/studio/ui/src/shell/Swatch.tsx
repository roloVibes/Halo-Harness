// A palette's swatch row (3.3.12.0 R1): surface, text, accent, accent-2, ok,
// warn and bad as chips, in the colours `GET settings/themes` sends for the
// palette (never a colour of this file: the chips read CSS variables set from
// the server's tokens, styles/themes.css draws them). The header's theme menu
// and Settings -> Themes both draw it.
import type { CSSProperties } from "react";
import { SWATCH, type Tokens } from "../lib/theme";

export function swatchVars(t: Tokens): CSSProperties {
  const out: Record<string, string> = {};
  for (const k of SWATCH) out[`--sw-${k}`] = t[k] || "";
  return out as CSSProperties;
}

export function Swatch({ tokens, big = false }: { tokens: Tokens; big?: boolean }) {
  return (
    <span className={"th-swatch" + (big ? " th-swatch-big" : "")} style={swatchVars(tokens)} aria-hidden="true" data-testid="theme-swatch">
      {SWATCH.map((k) => (
        <i key={k} className={`th-chip th-chip-${k}`} data-token={k} />
      ))}
    </span>
  );
}
