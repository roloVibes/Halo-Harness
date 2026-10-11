"""halo_harness.tui.theme_metroid -- the five Metroid area palettes (Halo
2.0.8 theme pack, round 2). Pure data: `tui/theme_games.py` serves the
palettes to the Textual stylesheet, `tui/hud_metroid.py` derives the HUD
colours and the area prefix glyph from the same tables.

Each area is one selectable variant of the single `metroid` theme (the
variant is `theme_variant` in ~/.halo/config.json, `/metroid <area>` sets
it): Crateria blues and greys, Brinstar greens and pinks, Norfair reds and
oranges, Maridia teals, Tourian greys. Original colour choices only; the
area names are plain words.

AREAS[name] = {"palette": the full Textual variable set,
               "border": HUD panel border colour, "glyph": the area prefix
               glyph shown in front of the AREA panel's value}.
"""

from __future__ import annotations

AREAS = {
    # Crateria: rain-dark blues and slate greys, power-suit orange accent.
    "crateria": {
        "palette": {
            "bridge-bg": "#0a1220", "bridge-surface": "#101b2f", "bridge-panel": "#17263f",
            "bridge-text": "#c9d8ec", "bridge-muted": "#6f86a6", "bridge-border": "#2f4a73",
            "bridge-accent": "#f09a2a", "bridge-success": "#58c27d", "bridge-warning": "#f2c14e",
            "bridge-error": "#ee5d6c", "bridge-user": "#5fd0c8", "bridge-assistant": "#c9d8ec",
            "bridge-tool": "#e0803a", "bridge-thinking": "#55698a",
        },
        "border": "#4f79b5", "glyph": "◇",
    },
    # Brinstar: overgrown greens with spore-pink highlights.
    "brinstar": {
        "palette": {
            "bridge-bg": "#0b1a12", "bridge-surface": "#12261a", "bridge-panel": "#1a3524",
            "bridge-text": "#d3ecd8", "bridge-muted": "#74a07f", "bridge-border": "#2f6b45",
            "bridge-accent": "#f06fb0", "bridge-success": "#6fd38a", "bridge-warning": "#e8d36a",
            "bridge-error": "#ee5d6c", "bridge-user": "#8fe3c0", "bridge-assistant": "#d3ecd8",
            "bridge-tool": "#e48ac0", "bridge-thinking": "#4f7a5c",
        },
        "border": "#3f9a62", "glyph": "◈",
    },
    # Norfair: heat-glow reds and oranges over a cooled-lava black.
    "norfair": {
        "palette": {
            "bridge-bg": "#1a0c09", "bridge-surface": "#28130e", "bridge-panel": "#3a1b13",
            "bridge-text": "#f2d9c4", "bridge-muted": "#b07a5e", "bridge-border": "#7a2f1c",
            "bridge-accent": "#ff7a2e", "bridge-success": "#c9c15a", "bridge-warning": "#ffb347",
            "bridge-error": "#ff4f4f", "bridge-user": "#ffc58a", "bridge-assistant": "#f2d9c4",
            "bridge-tool": "#ff9f5a", "bridge-thinking": "#8a5440",
        },
        "border": "#c4492a", "glyph": "◆",
    },
    # Maridia: deep-water teals and sea-glass greens.
    "maridia": {
        "palette": {
            "bridge-bg": "#06191c", "bridge-surface": "#0c2a2f", "bridge-panel": "#123a40",
            "bridge-text": "#cdeeee", "bridge-muted": "#6ba8ab", "bridge-border": "#1f6b72",
            "bridge-accent": "#2fd6c8", "bridge-success": "#6fe0a0", "bridge-warning": "#f0d27a",
            "bridge-error": "#ff6f7a", "bridge-user": "#9be8f0", "bridge-assistant": "#cdeeee",
            "bridge-tool": "#58c7e0", "bridge-thinking": "#4d8a8f",
        },
        "border": "#2e9ba3", "glyph": "≈",
    },
    # Tourian: cold machine greys with a pale warning glow.
    "tourian": {
        "palette": {
            "bridge-bg": "#111214", "bridge-surface": "#1a1c1f", "bridge-panel": "#25282c",
            "bridge-text": "#d5d8dc", "bridge-muted": "#8b9097", "bridge-border": "#4a4f57",
            "bridge-accent": "#e8e8ee", "bridge-success": "#9ac7a3", "bridge-warning": "#e6d28f",
            "bridge-error": "#e56a6a", "bridge-user": "#b9c4d6", "bridge-assistant": "#d5d8dc",
            "bridge-tool": "#c0c4cc", "bridge-thinking": "#686d75",
        },
        "border": "#7d838d", "glyph": "▣",
    },
}

DEFAULT_AREA = "crateria"
