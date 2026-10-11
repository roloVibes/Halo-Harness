"""halo_harness.tui.theme_mario -- the two Mario palettes (Halo 2.0.8 theme
pack, round 3). Pure data: `tui/theme_games.py` serves the palettes to the
Textual stylesheet, `tui/hud_mario.py` derives the HUD colours and the coin
glyph from the same table.

Each look is one selectable variant of the single `mario` theme (the variant
is `theme_variant` in ~/.halo/config.json, `/mario <variant>` sets it):

  bros   sky blue, brick red, pipe green and coin gold
  world  a brighter sky, question-block orange, feather yellow, pipe green

Original colour choices only; the variant names are plain words. Backgrounds
stay dark enough to read for hours, the sky shows up as the blue family.

LOOKS[name] = {"palette": the full Textual variable set, "border": HUD panel
               border colour, "glyph": the coin glyph in front of COINS}.
"""

from __future__ import annotations

LOOKS = {
    # Super Mario Bros: night-sky navy, brick-red borders, coin-gold accent.
    "bros": {
        "palette": {
            "bridge-bg": "#0e1830", "bridge-surface": "#15234a", "bridge-panel": "#1c2d5e",
            "bridge-text": "#f4f4f4", "bridge-muted": "#9db0e6", "bridge-border": "#b5471a",
            "bridge-accent": "#f8b830", "bridge-success": "#3fb83f", "bridge-warning": "#f8b830",
            "bridge-error": "#e8442c", "bridge-user": "#5cc8fc", "bridge-assistant": "#f4f4f4",
            "bridge-tool": "#e8651a", "bridge-thinking": "#6879b5",
        },
        "border": "#c4511f", "glyph": "●",
    },
    # Super Mario World: a brighter daytime sky, question-block orange
    # borders, feather-yellow accent, the same pipe green.
    "world": {
        "palette": {
            "bridge-bg": "#10305e", "bridge-surface": "#18407a", "bridge-panel": "#1f4f93",
            "bridge-text": "#fffbe6", "bridge-muted": "#a9c8f5", "bridge-border": "#e8821a",
            "bridge-accent": "#ffe14d", "bridge-success": "#46c25a", "bridge-warning": "#ffb020",
            "bridge-error": "#f2503a", "bridge-user": "#7fd6ff", "bridge-assistant": "#fffbe6",
            "bridge-tool": "#ff9a2e", "bridge-thinking": "#6f94d0",
        },
        "border": "#f08a1a", "glyph": "◉",
    },
}

DEFAULT_LOOK = "bros"
