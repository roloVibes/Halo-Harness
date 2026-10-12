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

# Beetlejuice (3.0.2.0): dusk purple with black-and-white stripe borders and
# a neon-green accent; `saturn` warms the surfaces toward the afterlife sand.
BEETLEJUICE = {
    "bridge-bg": "#130c1c", "bridge-surface": "#1c1228", "bridge-panel": "#241a34",
    "bridge-text": "#e6e0f0", "bridge-muted": "#9c8cb8", "bridge-border": "#b8b8c0",
    "bridge-accent": "#8cff4a", "bridge-success": "#8cff4a", "bridge-warning": "#e0a060",
    "bridge-error": "#ff4f6a", "bridge-user": "#c08aff", "bridge-assistant": "#e6e0f0",
    "bridge-tool": "#e0a060", "bridge-thinking": "#6a5a80",
}
BEETLEJUICE_SATURN = {**BEETLEJUICE, "bridge-bg": "#1c1210", "bridge-surface": "#2a1a14", "bridge-panel": "#36241a",
                      "bridge-muted": "#c09a70", "bridge-border": "#e0a060"}

# Alien (3.0.2.0): deep-space greys with CRT green text and accent; `hive`
# darkens the surfaces toward resin brown.
ALIEN = {
    "bridge-bg": "#090c0e", "bridge-surface": "#0f1518", "bridge-panel": "#141c20",
    "bridge-text": "#b8d8c0", "bridge-muted": "#5f7a6a", "bridge-border": "#3a4a50",
    "bridge-accent": "#58ff7a", "bridge-success": "#58ff7a", "bridge-warning": "#e0c060",
    "bridge-error": "#ff4040", "bridge-user": "#7ab8ff", "bridge-assistant": "#c0e0c8",
    "bridge-tool": "#9fb8a8", "bridge-thinking": "#3a5a48",
}
ALIEN_HIVE = {**ALIEN, "bridge-bg": "#0e0c08", "bridge-surface": "#171209", "bridge-panel": "#1f180c",
              "bridge-border": "#4a3a28", "bridge-muted": "#7a6a50"}

PALETTES = {"doom": DOOM, "metroid": METROID, "mario": MARIO, "beetlejuice": BEETLEJUICE, "alien": ALIEN}

VARIANT_PALETTES = {
    "metroid": {name: area["palette"] for name, area in AREAS.items()},
    "mario": {name: look["palette"] for name, look in LOOKS.items()},
    "beetlejuice": {"house": BEETLEJUICE, "saturn": BEETLEJUICE_SATURN},
    "alien": {"nostromo": ALIEN, "hive": ALIEN_HIVE},
}


def palette_for(name: str, variant: Optional[str] = None) -> dict:
    """The palette of game theme `name`; a known `variant` (a Metroid area,
    a Mario look) selects that variant's palette, anything else the
    theme's default."""
    variants = VARIANT_PALETTES.get(name) or {}
    return dict(variants.get(variant or "") or PALETTES[name])
