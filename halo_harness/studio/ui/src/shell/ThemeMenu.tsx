// The header's theme menu (3.3.12.0 R1): "Follow the system" and the ten
// palettes of the registry, each with its swatch row, the current one checked.
// A pick writes `theme` in ~/.halo/config.json through the settings route
// (lib/theme.ts chooseTheme), the one key the terminal reads too; a modifier
// already on (-daltonized, -ansi) stays on with the new palette. Settings ->
// Themes has the modifiers, the preview and the labels in full.
import { Icon } from "../lib/ui";
import { studio, useStore } from "../lib/store";
import { applyDoor } from "../routes/settings/door";
import { chooseTheme, FOLLOW, joinTheme, paletteOf, splitTheme, systemPosture, useThemes } from "../lib/theme";
import { Swatch } from "./Swatch";
import { useMenu } from "./useMenu";

export function ThemeMenu() {
  const theme = useStore(studio, (s) => s.theme);
  const palettes = useThemes((s) => s.info?.palettes);
  const { open, setOpen, box } = useMenu();
  const [base, mod] = splitTheme(theme);
  const following = theme === FOLLOW;
  const posture = following ? "" : paletteOf(theme)?.posture || systemPosture();
  const icon = following ? "auto" : posture === "light" ? "sun" : "moon";
  const label = following ? "follow the system" : theme;
  const pick = (name: string) => {
    setOpen(false);
    void chooseTheme(name);
  };
  return (
    <div className="menu-wrap" ref={box}>
      <button className="icon-btn icon-btn-lg" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}
              title={`Theme: ${label} (the terminal and Studio)`} aria-label="Theme" data-testid="theme-menu-btn" data-theme-now={theme}>
        <Icon name={icon} />
      </button>
      {open && (
        <div className="menu glass th-menu" role="menu" aria-label="Theme" data-testid="theme-menu">
          <button role="menuitemradio" aria-checked={following} className={"menu-item" + (following ? " on" : "")}
                  data-testid="theme-item" data-theme-id={FOLLOW} onClick={() => pick(FOLLOW)}>
            <Icon name="auto" />
            <span className="th-menu-name">Follow the system</span>
            <span className="menu-word">holo / paper</span>
          </button>
          {(palettes || []).map((p) => {
            const on = !following && p.id === base;
            return (
              <button key={p.id} role="menuitemradio" aria-checked={on} className={"menu-item" + (on ? " on" : "")} title={p.label}
                      data-testid="theme-item" data-theme-id={p.id} onClick={() => pick(joinTheme(p.id, mod))}>
                <Swatch tokens={p.tokens} />
                <span className="th-menu-name mono">{p.id}</span>
                <span className="menu-word">{p.posture}</span>
              </button>
            );
          })}
          {!palettes && <div className="menu-item muted">reading the palettes...</div>}
          <button role="menuitem" className="menu-item th-menu-more" data-testid="theme-menu-settings"
                  onClick={() => (setOpen(false), applyDoor({ group: "themes" }))}>
            <Icon name="settings" />
            <span className="th-menu-name">All themes and the modifiers</span>
          </button>
        </div>
      )}
    </div>
  );
}
