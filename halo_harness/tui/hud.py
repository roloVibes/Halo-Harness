"""halo_harness.tui.hud -- the game-HUD status-bar engine (Halo 2.0.8 theme
pack, round 1). Pure data and helpers, no Textual; `tui/hud_render.py` turns
a skin plus the live status fields into a `rich.text.Text`.

A skin is a DECLARATION, not a fork of the status bar:

    HudSkin(name, segments, strip, drop_order, faces, glyphs, glyphs_ascii,
            styles, face_styles, compact, compact_below, heavy_borders)

* `segments` -- the panel row, left to right. Each `Segment(slot, label,
  glyphs, width_min)` names one status-bar field by SLOT (the vocabulary is
  `SLOTS` below, produced by `StatusBar.hud_fields()`); `label` is the
  caption set into the panel's top border, `glyphs` an optional icon in
  front of the value, `width_min` the content width the panel keeps when the
  terminal narrows. The slot `face` is the phase face (not a field).
* `strip` -- the bottom border line: every other optional field (mode,
  effort, cwd, agents ...) as a ticker. Same `Segment` shape; items with no
  value are skipped.
* `drop_order` -- slots (panel or strip) removed first-to-last as the
  terminal narrows. A slot NOT listed is never dropped (the narrowest
  cascade keeps phase, context, cost, cwd, mode).
* `faces` -- phase state -> frames of an original ASCII face; the frame is
  picked by the spinner tick.
* `glyphs` / `glyphs_ascii` -- border, meter and face-brace sets; the ASCII
  set is used when the terminal has no truecolor.
* `compact` -- the slots kept on the single-line form used below
  `compact_below` columns.

Round 2 (Metroid) and round 3 (Mario) add a palette in `tui/theme_games.py`
and one `HudSkin` in their own module, registered with `register_skin`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from rich.cells import cell_len

# The slot vocabulary a skin may name (see StatusBar.hud_fields): `face` is
# drawn by the engine from the phase state, every other slot is a field.
SLOTS = (
    "model", "tokens", "context", "tools", "mcp", "cost", "providers", "cwd", "branch", "mode", "effort",
    "phase", "elapsed", "needs_you", "permission", "agents", "bg", "hang", "offline", "gov", "new",
    "throughput", "statusline", "face",
)
FACE_STATES = ("idle", "thinking", "writing", "error", "needs_you")


@dataclass(frozen=True)
class Segment:
    slot: str
    label: str = ""
    glyphs: str = ""
    width_min: int = 8


@dataclass(frozen=True)
class Glyphs:
    h: str
    v: str
    tl: str
    tr: str
    bl: str
    br: str
    tee_down: str
    tee_up: str
    meter_on: str
    meter_off: str
    meter_l: str = ""
    meter_r: str = ""
    face_l: str = "["
    face_r: str = "]"


@dataclass(frozen=True)
class HudField:
    """One status value. `long` is the full text, `short` the form used when
    space is tight (empty = none), `tone` picks the colour ("", ok, warn,
    bad, dim), `frac` (0..1) asks for a meter in front of the text."""
    long: str
    short: str = ""
    tone: str = ""
    frac: Optional[float] = None


@dataclass(frozen=True)
class HudSkin:
    name: str
    segments: tuple
    strip: tuple
    drop_order: tuple
    faces: dict
    glyphs: Glyphs
    glyphs_ascii: Glyphs
    styles: dict
    face_styles: dict = field(default_factory=dict)
    compact: tuple = ("face", "phase", "context", "cost", "mode", "cwd")
    compact_below: int = 46
    heavy_borders: bool = True
    rows: int = 3


_SKINS: dict = {}
_BUILTIN_SKIN_MODULES = ("halo_harness.tui.hud_doom",)
_loaded = False

# Themes that already have a palette but whose HUD skin is still to come:
# the status bar keeps the default layout and tints the model label with
# this accent. Filled by round 2 (metroid) and round 3 (mario), which move
# their entry into `register_skin`.
PLACEHOLDER_ACCENTS = {"metroid": "#f09a2a", "mario": "#f8b830"}


def register_skin(skin: HudSkin) -> None:
    _SKINS[skin.name] = skin


def skin_for(theme_name: Optional[str]) -> Optional[HudSkin]:
    """The HUD skin a theme renders through, or None for the default
    layout (every non-game theme, and the placeholder themes)."""
    global _loaded
    if not _loaded:
        _loaded = True
        import importlib
        for module in _BUILTIN_SKIN_MODULES:  # each registers its skin on import
            importlib.import_module(module)
    return _SKINS.get(theme_name or "")


def accent_for(theme_name: Optional[str]) -> Optional[str]:
    return PLACEHOLDER_ACCENTS.get(theme_name or "")


def face_state_for(phase: str, *, error: bool = False, needs_you: bool = False) -> str:
    """Phase -> face state. needs-you outranks error; error outranks the
    live phases; compacting counts as thinking, tool/running as writing."""
    if needs_you:
        return "needs_you"
    if error:
        return "error"
    if phase in ("thinking", "waiting", "compacting"):
        return "thinking"
    if phase in ("writing", "tool", "running"):
        return "writing"
    return "idle"


def clip(text: str, width: int) -> str:
    """Truncate `text` to `width` terminal cells, ending in an ellipsis."""
    if width <= 0:
        return ""
    if cell_len(text) <= width:
        return text
    out = ""
    for ch in text:
        if cell_len(out + ch) > width - 1:
            break
        out += ch
    return out + "…"


def pad(text: str, width: int) -> str:
    return text + " " * max(0, width - cell_len(text))


def ascii_only(text: str) -> str:
    return text.encode("ascii", "ignore").decode("ascii").strip()
