// Settings -> Themes (3.3.12.0 R1, `?mode=settings&page=themes`): the `theme`
// key of ~/.halo/config.json drawn as the eleven palettes of the registry, one
// row each with its swatch row (surface, text, accent, accent-2, ok, warn,
// bad, in the colours `GET settings/themes` sends), its posture and its label,
// the current one marked (3.3.15.0 R4: unset marks instrument, Halo's default);
// "Follow the system" above them, a choice that saves `theme: auto`; the -daltonized and
// -ansi modifiers as two toggles. Pointing at a row previews it on this page,
// Esc puts the saved one back, a click saves it (themePage.ts). 3.3.12.0 R2:
// an enabled pack's palettes follow under the pack's id, drawn the same way.
import { FOLLOW, groupPalettes, splitTheme, useThemes, type Palette } from "../../lib/theme";
import { studio, useStore } from "../../lib/store";
import { HELP } from "../help";
import { Swatch } from "../../shell/Swatch";
import { Head } from "./SettingsPage";
import { endPreview, preview, save, toggleModifier, usePreviewRevert } from "./themePage";

const MOD_WORDS: Record<string, [string, string]> = {
  daltonized: ["Daltonized", "blue and orange for the accents and the status colours, never red against green"],
  ansi: ["ANSI", "the 16 colours a terminal without truecolor draws; Studio stays in full colour"],
};

function Modifiers({ mod, following }: { mod: string; following: boolean }) {
  return (
    <div className="th-mods" data-testid="theme-mods">
      {Object.entries(MOD_WORDS).map(([m, [title, words]]) => (
        <label key={m} className="th-mod" data-disabled={following || undefined} title={following ? "Pick a palette first" : words}>
          <input type="checkbox" checked={mod === m} disabled={following} data-testid="theme-mod" data-mod={m}
                 onChange={(e) => toggleModifier(m, e.target.checked)} />
          <span className="th-mod-title">{title}</span>
          <span className="th-mod-words muted">{words}</span>
        </label>
      ))}
    </div>
  );
}

function Row({ p, on, mod, previewing }: { p: Palette; on: boolean; mod: string; previewing: string }) {
  return (
    <button type="button" role="radio" aria-checked={on} className="th-row" data-testid="theme-row" data-theme-id={p.id}
            data-current={on || undefined} data-preview={previewing && splitTheme(previewing)[0] === p.id ? true : undefined}
            title={p.pack ? p.id : undefined} onMouseEnter={() => preview(p.id)} onFocus={() => preview(p.id)} onClick={() => save(p.id)}>
      <Swatch tokens={mod === "daltonized" ? p.daltonized : p.tokens} big />
      <span className="th-row-name mono">{p.local_id || p.id}</span>
      <span className="th-row-posture mono" data-posture={p.posture}>{p.posture}</span>
      <span className="th-row-label muted">{p.label}</span>
      {on && <span className="th-row-mark mono" data-testid="theme-current">CURRENT</span>}
    </button>
  );
}

export function ThemesPage() {
  usePreviewRevert();
  const theme = useStore(studio, (s) => s.theme);
  const info = useThemes((s) => s.info);
  const error = useThemes((s) => s.error);
  const previewing = useThemes((s) => s.preview);
  const following = theme === FOLLOW;
  const [base, mod] = splitTheme(theme);
  const h = HELP["settings-themes"] || { about: "", help: "" };
  // 3.3.15.0 R4: unset is Halo's default (instrument), Follow the system is the saved `theme: auto`
  const cli = info && info.theme === null
    ? `theme unset in ~/.halo/config.json: Halo's default, ${info.default || theme}`
    : `halo config set theme ${theme} (halo config unset theme: the default)`;
  return (
    <section className="st-page-card" data-testid="settings-group-page" data-group="themes" aria-label="Settings: Themes">
      <Head title="Themes" about={h.about} help={h.help} count={`${info?.palettes.length ?? 10} PALETTES`} />
      {error && <p className="st-error">Studio could not read the palettes: {error}</p>}
      {!info && !error && <div className="mono muted">reading the palettes...</div>}
      {info && (
        <>
          <Modifiers mod={mod} following={following} />
          <div className="th-list" role="radiogroup" aria-label="Theme" data-testid="theme-list" onMouseLeave={endPreview}>
            <button type="button" role="radio" aria-checked={following} className="th-row th-row-follow" data-testid="theme-row"
                    data-theme-id={FOLLOW} data-current={following || undefined} onMouseEnter={() => preview(FOLLOW)} onClick={() => save(FOLLOW)}>
              <span className="th-row-name">Follow the system</span>
              <span className="th-row-label muted">{info.follow.dark} on a dark system, {info.follow.light} on a light one</span>
              {following && <span className="th-row-mark mono" data-testid="theme-current">CURRENT</span>}
            </button>
            {groupPalettes(info.palettes).map((g) => (
              <div key={g.pack || "core"} className="th-list" role="group" aria-label={g.pack ? `From the pack ${g.pack}` : "Palettes"}
                   data-testid="theme-group" data-pack={g.pack || undefined}>
                {g.pack && (
                  <div className="th-group" data-testid="theme-group-name">
                    <span className="mono">{g.pack}</span>
                    {g.name !== g.pack && <span className="th-group-name">{g.name}</span>}
                    <span className="th-group-name">turning the pack off puts the palette before it back</span>
                  </div>
                )}
                {g.palettes.map((p) => (
                  <Row key={p.id} p={p} on={!following && p.id === base} mod={mod} previewing={previewing} />
                ))}
              </div>
            ))}
          </div>
          <p className="st-cli mono muted" data-testid="theme-cli">{cli} · /theme &lt;name&gt; in a session</p>
        </>
      )}
    </section>
  );
}
