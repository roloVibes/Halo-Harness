// setup-theme (3.3.0.0 R1): the `theme` key -- 3.3.12.0 R1: each of the ten
// palettes as a swatch drawn in the colours the terminal uses for it
// (tui/theme.py variables_for, served in the state); Save writes `theme` in
// ~/.halo/config.json, the one key the terminal and Studio both draw from.
// The -daltonized / -ansi modifiers and a live preview are Settings -> Themes.
import type { CSSProperties } from "react";
import { BlockFoot, useLoadState, Waiting } from "./BlockFoot";
import { NONE, pick, shownOf, useSetup, type ThemeRow } from "./store";

/** The swatch's own colours: CSS variables set from the server's palette (the stylesheet reads only those). */
function vars(t: ThemeRow): CSSProperties {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(t.palette)) out[`--sw-${k}`] = v;
  return out as CSSProperties;
}

function Swatch({ t, on }: { t: ThemeRow; on: boolean }) {
  return (
    <label className="su-swatch" data-on={on || undefined} data-testid="setup-theme-swatch" data-name={t.name} style={vars(t)}>
      <input type="radio" name="setup-theme" checked={on} onChange={() => pick("theme", t.name)} data-testid="setup-theme-input" data-name={t.name} />
      <span className="su-sw-screen mono" aria-hidden="true">
        <span className="su-sw-line">
          <span className="su-sw-user">&gt; </span>fix the failing test
        </span>
        <span className="su-sw-line su-sw-tool">Bash(npm test)</span>
        <span className="su-sw-dots">
          <i className="su-sw-ok" />
          <i className="su-sw-warn" />
          <i className="su-sw-bad" />
          <i className="su-sw-accent" />
        </span>
      </span>
      <span className="su-sw-name mono">{t.name}</span>
    </label>
  );
}

export function ThemeDetail() {
  const { ready, error } = useLoadState();
  const themes = useSetup((s) => s.data?.themes || NONE);
  const shown = useSetup((s) => shownOf(s, "theme"));
  const saved = useSetup((s) => s.data?.theme || "");
  if (!ready) return <Waiting error={error} />;
  return (
    <div className="su-block" data-testid="setup-theme">
      <p className="su-lead muted" data-testid="setup-theme-note">
        One palette for halo in your terminal and for Studio. Settings -&gt; Themes has the colour-blind and 16-colour modifiers and a live preview.
        {saved ? "" : " Nothing saved yet: the terminal uses claude-dark and Studio follows the system."}
      </p>
      <div className="su-swatches" role="radiogroup" aria-label="Theme">
        {themes.map((t) => (
          <Swatch key={t.name} t={t} on={shown === t.name} />
        ))}
      </div>
      <BlockFoot block="theme" what="halo config set theme <name> (or /theme in a session)" />
    </div>
  );
}

export function ThemeGlance() {
  const shown = useSetup((s) => s.data?.theme || s.data?.theme_default || "");
  return (
    <div className="glance">
      <div className="glance-kicker mono">THEME</div>
      <div className="glance-text">{shown}</div>
      <div className="glance-hint">theme in config.json</div>
    </div>
  );
}
