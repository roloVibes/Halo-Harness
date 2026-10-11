"""halo_harness.tui.theme_games -- Textual CSS palettes for the three game
themes (Halo 2.0.8 theme pack). Same key set as the base palettes in
`tui/theme.py`; `variables_for` picks from here by name.

Original colour choices only, inspired by each game's mood. A palette is
the whole of a skin's colour story: the status-bar layout lives in
`tui/hud.py` + `tui/hud_doom.py`, so a new game theme is one palette dict
here plus one `HudSkin` declaration.
"""

from __future__ import annotations

# DOOM: dark greys, blood reds, rust browns, muted greens, amber text.
DOOM = {
    "bridge-bg": "#12100e", "bridge-surface": "#1b1815", "bridge-panel": "#241f1a",
    "bridge-text": "#d9a441", "bridge-muted": "#8a7357", "bridge-border": "#7a3b22",
    "bridge-accent": "#c8372d", "bridge-success": "#7f9a4b", "bridge-warning": "#e8b04a",
    "bridge-error": "#ff5a45", "bridge-user": "#a9b86a", "bridge-assistant": "#e0b565",
    "bridge-tool": "#c9773b", "bridge-thinking": "#5f5044",
}

# Metroid: Crateria blues and greys with a power-suit orange accent.
# Round 2 refines this (per-area accents) and adds the suit-HUD skin; until
# then the status bar uses the default layout tinted with this accent.
METROID = {
    "bridge-bg": "#0a1220", "bridge-surface": "#101b2f", "bridge-panel": "#17263f",
    "bridge-text": "#c9d8ec", "bridge-muted": "#6f86a6", "bridge-border": "#2f4a73",
    "bridge-accent": "#f09a2a", "bridge-success": "#58c27d", "bridge-warning": "#f2c14e",
    "bridge-error": "#ee5d6c", "bridge-user": "#5fd0c8", "bridge-assistant": "#c9d8ec",
    "bridge-tool": "#e0803a", "bridge-thinking": "#55698a",
}

# Mario: sky blue, brick red, pipe green, coin gold, question-block orange.
# Round 3 refines this and adds the world-and-coins skin; until then the
# status bar uses the default layout tinted with this accent.
MARIO = {
    "bridge-bg": "#0e1830", "bridge-surface": "#15234a", "bridge-panel": "#1c2d5e",
    "bridge-text": "#f4f4f4", "bridge-muted": "#9db0e6", "bridge-border": "#b5471a",
    "bridge-accent": "#f8b830", "bridge-success": "#3fb83f", "bridge-warning": "#f8b830",
    "bridge-error": "#e8442c", "bridge-user": "#5cc8fc", "bridge-assistant": "#f4f4f4",
    "bridge-tool": "#e8651a", "bridge-thinking": "#6879b5",
}

PALETTES = {"doom": DOOM, "metroid": METROID, "mario": MARIO}
