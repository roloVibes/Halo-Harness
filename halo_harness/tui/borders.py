"""halo_harness.tui.borders -- extra Textual border types for the game
skins (Halo 2.0.8 theme pack, round 3).

`brick` is the Mario skin's card and dialog border: a medium-shade wall,
drawn in the theme's border colour (brick red / question-block orange), with
the same shape as the built-in `solid` type. Textual keeps its border tables
in module-level dicts and validates a stylesheet's `border:` type against a
set, so registering a type is adding one entry to each; `textual` is pinned
in pyproject.toml and `tests/test_hud_mario.py` pins that the type parses and
renders. Imported by `tui/app.py` before the stylesheet is read; the brick
rules live in `styles_brick.tcss`, loaded only when `BRICK_READY`.
"""

from __future__ import annotations

BRICK_CHARS = (("▒", "▒", "▒"), ("▒", " ", "▒"), ("▒", "▒", "▒"))
BRICK_LOCATIONS = ((0, 0, 0), (0, 0, 0), (0, 0, 0))


def register_border_types() -> bool:
    """Add the extra types; True when `brick` is usable. Never raises."""
    try:
        from textual._border import BORDER_CHARS, BORDER_LOCATIONS
        from textual.css.constants import VALID_BORDER
        BORDER_CHARS.setdefault("brick", BRICK_CHARS)
        BORDER_LOCATIONS.setdefault("brick", BRICK_LOCATIONS)
        if isinstance(VALID_BORDER, set):
            VALID_BORDER.add("brick")
        return "brick" in BORDER_CHARS and "brick" in VALID_BORDER
    except Exception:
        return False


BRICK_READY = register_border_types()
