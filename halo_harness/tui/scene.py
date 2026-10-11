"""halo_harness.tui.scene -- the level-band engine (Halo 2.0.11 round A3).

A game theme can declare a `Scene`: a three-row strip above the prompt that
looks like a side-scrolling level -- a hero sprite, scenery that scrolls
while the model writes, an enemy that crosses the screen, a cue sprite
when a sub-agent finishes. Pure data and one render function; no Textual
here (`tui/widgets/scene_band.py` owns the timer and the widget).

Pixels: the band is 6 px tall (ROWS cells, two px per cell through the
half-block glyphs ▀ ▄ █) and one px per column wide. A sprite is a tuple
of rows of palette letters (`"."` is transparent); `Scene.colors` maps a
letter to a hex colour. All art is original: silhouettes in the spirit of
the 8-bit era, nothing copied from any game.

`render_scene(scene, width, phase=..., frame=..., scroll=..., ...)` is a
pure function: `frame` is the animation tick (the widget advances it
while a turn is live), `scroll` the pixels the ground has travelled (it
advances only in `scene.scroll_phases`). Phases are the HUD's face states
(`hud.face_state_for`): idle, thinking, writing, error, needs_you.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from rich.style import Style
from rich.text import Text

ROWS = 3
HEIGHT = ROWS * 2
PHASES = ("idle", "thinking", "writing", "error", "needs_you")

Sprite = tuple[str, ...]


@dataclass(frozen=True)
class Layer:
    """Scenery repeated along the ground: one of `sprites` every `spacing`
    px (picked by position, so the mix is stable), bottom-aligned at
    `y` rows from the band's bottom (0 sits on the ground), scrolling at
    `speed` times the ground (clouds drift slower)."""
    sprites: tuple[Sprite, ...]
    spacing: int
    speed: float = 1.0
    y: int = 0


@dataclass(frozen=True)
class Mover:
    """The enemy: crosses right to left at `speed` px per frame while the
    phase is one of `phases`, cycling `frames`; `y` as for a Layer."""
    frames: tuple[Sprite, ...]
    phases: frozenset
    speed: int = 2
    y: int = 0


@dataclass(frozen=True)
class Scene:
    name: str
    colors: Mapping[str, str]
    ground: Sprite                       # a repeating tile, bottom-aligned
    hero: Mapping[str, tuple[Sprite, ...]]  # phase -> frames; "idle" is the fallback
    ascii: Mapping[str, tuple[str, ...]]    # "hero", "mover", "tile": 3 rows each; "ground": one char
    hero_x: int = 8
    layers: tuple[Layer, ...] = ()
    mover: Optional[Mover] = None
    cues: Mapping[str, Sprite] = field(default_factory=dict)
    scroll_phases: frozenset = frozenset({"writing"})
    variants: Mapping[str, Mapping[str, str]] = field(default_factory=dict)  # variant -> colour overrides


def _stamp(buf, sprite: Sprite, x: int, bottom: int, colors, width: int) -> None:
    """Draw `sprite` with its last row on pixel row `bottom` (inclusive)."""
    top = bottom - len(sprite) + 1
    for r, row in enumerate(sprite):
        py = top + r
        if not 0 <= py < HEIGHT:
            continue
        for c, letter in enumerate(row):
            px = x + c
            if letter != "." and 0 <= px < width:
                buf[py][px] = colors.get(letter)


def _ground_rows(scene: Scene) -> int:
    return len(scene.ground)


def _layers(buf, scene, width, scroll, colors) -> None:
    base = HEIGHT - _ground_rows(scene) - 1
    for layer in scene.layers:
        shift = int(scroll * layer.speed)
        first = -(shift % layer.spacing) - layer.spacing
        for x in range(first, width + layer.spacing, layer.spacing):
            k = (x + shift) // layer.spacing
            sprite = layer.sprites[k % len(layer.sprites)]
            _stamp(buf, sprite, x, base - layer.y, colors, width)


def _mover_x(mover: Mover, frame: int, width: int) -> int:
    span = width + 12
    return width - ((frame * mover.speed) % span)


def hero_frame(scene: Scene, phase: str, frame: int) -> Sprite:
    frames = scene.hero.get(phase) or scene.hero.get("idle") or (("",),)
    return frames[frame % len(frames)]


def scene_colors(scene: Scene, variant: str = "") -> dict:
    colors = dict(scene.colors)
    colors.update(scene.variants.get(variant or "", {}))
    return colors


def render_pixels(scene: Scene, width: int, *, phase: str = "idle", frame: int = 0, scroll: int = 0,
                  cue: str = "", variant: str = "") -> list:
    """The 6 x width pixel buffer (hex colour or None for the sky)."""
    colors = scene_colors(scene, variant)
    buf = [[None] * width for _ in range(HEIGHT)]
    ground_h = _ground_rows(scene)
    tile_w = max(1, len(scene.ground[0]))
    start = -(scroll % tile_w)
    for x in range(start, width, tile_w):
        _stamp(buf, scene.ground, x, HEIGHT - 1, colors, width)
    _layers(buf, scene, width, scroll, colors)
    base = HEIGHT - ground_h - 1
    if scene.mover is not None and phase in scene.mover.phases:
        mv = scene.mover
        _stamp(buf, mv.frames[frame % len(mv.frames)], _mover_x(mv, frame, width), base - mv.y, colors, width)
    hero = hero_frame(scene, phase, frame)
    _stamp(buf, hero, scene.hero_x, base, colors, width)
    if cue and cue in scene.cues:
        sprite = scene.cues[cue]
        _stamp(buf, sprite, scene.hero_x + len(hero[0]) + 1, base - 1, colors, width)
    return buf


def _cell(top, bot, bg: str):
    if top is None and bot is None:
        return " ", Style(bgcolor=bg)
    if top == bot:
        return "█", Style(color=top, bgcolor=bg)
    if bot is None:
        return "▀", Style(color=top, bgcolor=bg)
    if top is None:
        return "▄", Style(color=bot, bgcolor=bg)
    return "▀", Style(color=top, bgcolor=bot)


def pixels_to_text(buf, bg: str) -> Text:
    width = len(buf[0]) if buf else 0
    text = Text(no_wrap=True, overflow="crop")
    for row in range(ROWS):
        if row:
            text.append("\n")
        run, run_style = "", None
        for col in range(width):
            ch, style = _cell(buf[2 * row][col], buf[2 * row + 1][col], bg)
            if style == run_style:
                run += ch
            else:
                if run:
                    text.append(run, run_style)
                run, run_style = ch, style
        if run:
            text.append(run, run_style)
    return text


def render_ascii(scene: Scene, width: int, *, phase: str = "idle", frame: int = 0, scroll: int = 0) -> Text:
    """The no-truecolor form: three rows of plain characters, the same
    positions, no colour."""
    rows = [[" "] * width for _ in range(ROWS)]

    def put(art, x, bottom_row=ROWS - 1):
        top = bottom_row - len(art) + 1
        for r, line in enumerate(art):
            for c, ch in enumerate(line):
                px, py = x + c, top + r
                if ch != " " and 0 <= px < width and 0 <= py < ROWS:
                    rows[py][px] = ch

    ground = scene.ascii.get("ground", ("=",))[0]
    rows[ROWS - 1] = list((ground * width)[:width])
    tile = scene.ascii.get("tile")
    if tile:
        spacing = max(len(tile[0]) + 10, 16)
        first = -(scroll % spacing) - spacing
        for x in range(first, width + spacing, spacing):
            put(tile, x, ROWS - 2)
    mover = scene.ascii.get("mover")
    if mover and scene.mover is not None and phase in scene.mover.phases:
        put(mover, _mover_x(scene.mover, frame, width), ROWS - 2)
    hero = scene.ascii.get("hero", ("o", "|", "^"))
    put(hero, scene.hero_x, ROWS - 2)
    text = Text(no_wrap=True, overflow="crop")
    for r, row in enumerate(rows):
        if r:
            text.append("\n")
        text.append("".join(row)[:width])
    return text


def render_scene(scene: Scene, width: int, *, phase: str = "idle", frame: int = 0, scroll: int = 0,
                 ascii_mode: bool = False, cue: str = "", bg: str = "#000000", variant: str = "") -> Text:
    """The band for `width` columns: ROWS rows, every row exactly `width`
    cells, the sky painted `bg` (the theme's background, so the band sits
    flush with the transcript)."""
    width = max(1, int(width or 80))
    if ascii_mode:
        return render_ascii(scene, width, phase=phase, frame=frame, scroll=scroll)
    buf = render_pixels(scene, width, phase=phase, frame=frame, scroll=scroll, cue=cue, variant=variant)
    return pixels_to_text(buf, bg)


_SCENES: dict = {}


def register_scene(scene: Scene) -> Scene:
    _SCENES[scene.name] = scene
    return scene


def scene_for(theme: str) -> Optional[Scene]:
    """The scene of game theme `theme`, importing its module on first use
    (the same lazy pattern as `hud.skin_for`); None for a theme without one."""
    if theme not in _SCENES and theme in ("doom", "metroid", "mario"):
        import importlib
        importlib.import_module(f"halo_harness.tui.scene_{theme}")
    return _SCENES.get(theme)
