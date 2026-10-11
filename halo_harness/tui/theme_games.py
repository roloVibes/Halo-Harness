"""halo_harness.tui.theme_games -- Textual CSS palettes for the three game
themes (Halo 2.0.8 theme pack). Same key set as the base palettes in
`tui/theme.py`; `variables_for` picks from here by name.

Original colour choices only, inspired by each game's mood. A palette is
the whole of a skin's colour story: the status-bar layout lives in
`tui/hud.py` + `tui/hud_doom.py` / `hud_metroid.py` / `hud_mario.py`, so a new game theme is
one palette dict here plus one `HudSkin` declaration.
"""

from __future__ import annotations

from typing import Optional

from halo_harness.tui.theme_mario import DEFAULT_LOOK, LOOKS
from halo_harness.tui.theme_metroid import AREAS, DEFAULT_AREA

# DOOM: dark greys, blood reds, rust browns, muted greens, amber text.
DOOM = {
    "bridge-bg": "#12100e", "bridge-surface": "#1b1815", "bridge-panel": "#241f1a",
    "bridge-text": "#d9a441", "bridge-muted": "#8a7357", "bridge-border": "#7a3b22",
    "bridge-accent": "#c8372d", "bridge-success": "#7f9a4b", "bridge-warning": "#e8b04a",
    "bridge-error": "#ff5a45", "bridge-user": "#a9b86a", "bridge-assistant": "#e0b565",
    "bridge-tool": "#c9773b", "bridge-thinking": "#5f5044",
}

# Metroid: five area palettes (Crateria blues and greys with a power-suit
# orange accent, Brinstar, Norfair, Maridia, Tourian), see tui/theme_metroid.py.
# `METROID` is the default (Crateria) palette; `palette_for` picks a variant.
METROID = AREAS[DEFAULT_AREA]["palette"]

# Mario: two looks (bros, world), see tui/theme_mario.py. `MARIO` is the
# default (bros) palette; `palette_for` picks a variant.
MARIO = LOOKS[DEFAULT_LOOK]["palette"]

PALETTES = {"doom": DOOM, "metroid": METROID, "mario": MARIO}

VARIANT_PALETTES = {
    "metroid": {name: area["palette"] for name, area in AREAS.items()},
    "mario": {name: look["palette"] for name, look in LOOKS.items()},
}


def palette_for(name: str, variant: Optional[str] = None) -> dict:
    """The palette of game theme `name`; a known `variant` (a Metroid area,
    a Mario look) selects that variant's palette, anything else the
    theme's default."""
    variants = VARIANT_PALETTES.get(name) or {}
    return dict(variants.get(variant or "") or PALETTES[name])
