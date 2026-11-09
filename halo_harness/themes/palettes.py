"""halo_harness.themes.palettes -- the eleven palettes as data (Halo 3.3.12.0 R1; 3.3.15.0 L1 added `instrument`;
docs/CONFIG.md `theme`).

One token vocabulary for the terminal and Studio; `registry.py` reads this module, `tui/theme.py` maps the tokens to
Textual's variables and `scripts/themes_css.py` writes Studio's `[data-theme]` blocks in `styles/tokens.css` from it,
so a colour lives here and nowhere else. Python data rather than one JSON per palette: no package-data entry, no file
read at import, and the drift test and the contrast pins import it directly; a pack's own themes (R2) register into
the registry from the pack's manifest at run time, not into this file.

A palette is `{id, label, posture: dark | light, tokens}` with every name of `TOKENS`, each a `#rrggbb`.
"""

from __future__ import annotations

# The vocabulary: (token, what it colours). Studio derives its glass, glows, soft fills and scrim from these by
# posture (scripts/themes_css.py); the terminal reads the opaque ones (tui/theme.py).
TOKENS = (
    ("bg", "the page behind everything"),
    ("bg2", "the second band: Studio's canvas, the terminal's surface"),
    ("surface", "a panel's or a card's face (Studio)"),
    ("surface2", "a raised face: hover, inputs, the terminal's panels"),
    ("border", "an opaque edge (the terminal's borders)"),
    ("line", "the tint Studio's lines and grid are drawn in (dark: with alpha; light: as is)"),
    ("text", "body text"),
    ("muted", "secondary text: hints, labels"),
    ("faint", "decoration: dim text, the strong line on a light page"),
    ("accent", "this is live / do this"),
    ("accent2", "the second accent"),
    ("accent_ink", "text on an accent fill (a primary button)"),
    ("ok", "done, healthy"),
    ("warn", "needs you"),
    ("bad", "failed"),
    ("user", "the user's lines in the terminal"),
    ("tool", "a tool call in the terminal"),
)
TOKEN_NAMES = tuple(name for name, _ in TOKENS)

MODIFIERS = ("daltonized", "ansi")

# The default when `theme` is unset: Studio follows the system (dark -> instrument since 3.3.15.0 L1, holo before;
# light -> paper); the terminal keeps its own default (theme.DEFAULT_THEME, truecolor-aware).
FOLLOW_DARK = "instrument"
FOLLOW_LIGHT = "paper"


def _p(pid: str, label: str, posture: str, *values: str) -> dict:
    return {"id": pid, "label": label, "posture": posture, "tokens": dict(zip(TOKEN_NAMES, values))}


# claude-dark and claude-light keep the terminal's colours of before; claude-light's ok, warn and tool are a shade
# darker than Latte's (3.3.12.0: each reads 3:1 on the page, tests/test_theme_registry.py pins it). holo and
# claude-light are Studio's dark and light of before (claude-light's surface2 is the terminal's panel colour).
#                 bg         bg2        surface    surface2   border     line       text       muted      faint
#                 accent     accent2    accent_ink ok         warn       bad        user       tool
PALETTES = (
    _p("claude-dark", "The terminal's classic dark: Catppuccin Mocha", "dark",
       "#1e1e2e", "#282838", "#2a2a3c", "#313244", "#45475a", "#a6adc8", "#cdd6f4", "#7f849c", "#585b70",
       "#89b4fa", "#cba6f7", "#1e1e2e", "#a6e3a1", "#f9e2af", "#f38ba8", "#94e2d5", "#fab387"),
    _p("claude-light", "The terminal's classic light: Catppuccin Latte", "light",
       "#eff1f5", "#e6e9ef", "#ffffff", "#dce0e8", "#ccd0da", "#ccd0da", "#4c4f69", "#6c6f85", "#9ca0b0",
       "#1e66f5", "#8839ef", "#ffffff", "#3b9428", "#b67418", "#d20f39", "#179299", "#e45401"),
    _p("holo", "Studio's look before 3.3.15.0: navy, cyan and amber", "dark",
       "#070b14", "#0b1222", "#0e1628", "#142038", "#2d4b64", "#78c8ff", "#dbe7ff", "#7d8fb3", "#4a5878",
       "#39d7ff", "#7c8cff", "#04121c", "#4ef0a8", "#ffb347", "#ff4d8d", "#7ce3ff", "#ffb347"),
    # 3.3.15.0 L1: the Instrument look's palette (docs/design/studio-instrument/PROPOSAL.md section 1), Studio's dark default
    _p("instrument", "Studio's instrument panel: solid near-black, hairlines, cyan works, amber waits", "dark",
       "#07090c", "#0b0e12", "#0f1318", "#151a21", "#232a33", "#1a2028", "#e6edf3", "#9aa6b2", "#7d8995",
       "#22d3ee", "#f5a524", "#031317", "#3dd68c", "#f5a524", "#ff5c6a", "#a78bfa", "#67e8f9"),
    _p("paper", "Warm paper and ink-blue, for daylight", "light",
       "#f7f3ea", "#efe9dc", "#fffdf8", "#e8e0cf", "#d9cfbb", "#d9cfbb", "#3b3024", "#6b5d4b", "#a89a85",
       "#1d5c8c", "#a04a26", "#ffffff", "#2d7236", "#8f5b00", "#b3261e", "#1d6b6b", "#9a4612"),
    _p("midnight", "Deep blue night, a calm blue accent", "dark",
       "#0a0f1f", "#0e1529", "#121b33", "#1a2542", "#2a3a63", "#6f8fd8", "#dce4f7", "#8a99bf", "#4c5a80",
       "#5b9dff", "#a78bfa", "#061024", "#5fd39a", "#f2c14e", "#ff6b81", "#7fb3ff", "#f2a65a"),
    _p("ember", "Red and orange on charred black: review and engagement work", "dark",
       "#140a08", "#1b0e0b", "#22120e", "#2e1913", "#4a2a20", "#ff8a5c", "#f6e2d8", "#b9907f", "#6e4a3e",
       "#ff5a36", "#ffa630", "#1a0805", "#8fd694", "#ffc857", "#ff4d5e", "#ff8a5c", "#ffa630"),
    _p("forest", "Pine greens, a gold second accent", "dark",
       "#0b130e", "#0f1a13", "#132219", "#1a2e22", "#2b4a37", "#7fd6a0", "#dcefe2", "#8fb09a", "#4e6b58",
       "#4fd18b", "#c8d65a", "#05140b", "#7be495", "#f0c75e", "#ff7a6b", "#8be0b4", "#e8b45a"),
    _p("slate", "Quiet greys, low saturation, for long reading", "light",
       "#f3f4f6", "#e9ebee", "#ffffff", "#dfe2e6", "#cfd4da", "#cfd4da", "#2e3440", "#5f6773", "#a0a7b1",
       "#46627f", "#6e5f80", "#ffffff", "#3d7550", "#85641a", "#a8433f", "#3d6a73", "#8a5a3a"),
    _p("dusk", "Violet evening, a pink second accent", "dark",
       "#120e1c", "#171226", "#1d162f", "#271e3d", "#3d3160", "#b59cff", "#e8e0fa", "#a497c4", "#5e5280",
       "#a68bff", "#ff8fd0", "#140c26", "#74e0b0", "#ffcf70", "#ff6f91", "#c4b0ff", "#ffa98a"),
    _p("dawn", "Rose and gold morning light", "light",
       "#fbf3f1", "#f5e8e5", "#fffaf8", "#efdcd8", "#e8cfc9", "#e8cfc9", "#43262b", "#7a5560", "#b89aa0",
       "#b8336a", "#946000", "#ffffff", "#2f7d4f", "#8f5600", "#b42318", "#8e3a6b", "#94520a"),
)

# `-ansi`: the 16-colour set a terminal without truecolor draws, one per posture (as before 3.3.12.0).
ANSI = {
    "dark": dict(zip(TOKEN_NAMES, (
        "#000000", "#000000", "#000000", "#000000", "#808080", "#808080", "#ffffff", "#808080", "#808080",
        "#00ffff", "#ff00ff", "#000000", "#00ff00", "#ffff00", "#ff0000", "#00ffff", "#ff00ff"))),
    "light": dict(zip(TOKEN_NAMES, (
        "#ffffff", "#ffffff", "#ffffff", "#ffffff", "#808080", "#808080", "#000000", "#808080", "#808080",
        "#0000ff", "#800080", "#ffffff", "#008000", "#808000", "#ff0000", "#008080", "#800080"))),
}

# `-daltonized`: a deuteranopia-safe pair, blue and orange (the Okabe-Ito hues), never red against green. The
# registry moves each hue's lightness per palette until it reads on that palette's backgrounds.
DALTONIZED_HUES = {"blue": "#56b4e9", "orange": "#e69f00", "vermillion": "#d55e00"}
