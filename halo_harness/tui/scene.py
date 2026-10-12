"""halo_harness.tui.scene -- the level-band engine (Halo 2.0.11 round A3,
rebuilt in 3.0.2.0 "the levels, second generation").

A game theme declares a `Scene`: a strip above the prompt that plays like a
16-bit side-scroller. Six terminal rows hold twelve pixel rows (two per cell
through the half-block glyphs); one pixel per column. A sprite is a tuple
of rows of palette letters (`.` is transparent). Uppercase letters are the
palette, and a lowercase letter that the palette does not name is the
darker shade of its uppercase, so art carries its own shadows.

What a scene can have, all pure data (the themes live in scene_mario.py,
scene_metroid.py and scene_doom.py; `scene_fx.py` holds shading, lights
and projectiles; `scene_text.py` turns pixels into Rich text):

- `sky`: a vertical gradient (one hex per pixel row) behind everything;
- `ground`: an animated tile (frames), bottom-aligned;
- `layers`: parallax scenery at its own speed and height, optionally
  blinking (`twinkle`) or casting light (`light`);
- `hero`: frames per phase, a `jump` table while writing, a `flash`
  (muzzle, every N frames, with a light) and a `hero_shot` (a projectile
  fired to the right while writing);
- `mover`: the enemy crossing right to left in its phases, with a sine
  `bob` and its own `shot` fired to the left;
- `cues`: a sprite shown beside the hero for a moment (agent done, job done).

`render_pixels` returns the 12 x width colour buffer; `render_scene` the
Rich Text. Both are pure functions of (phase, frame, scroll, cue, variant),
so captures are deterministic. All art is original: silhouettes in the
spirit of the 16-bit era, nothing copied from any game.
"""

from __future__ import annotations

import math
from typing import Optional

from rich.text import Text

ROWS = 6
HEIGHT = ROWS * 2
PHASES = ("idle", "thinking", "writing", "error", "needs_you")

from halo_harness.tui.scene_model import Flash, Layer, Mover, Scene, Shot, Sprite  # noqa: F401  (re-exported)


# -- drawing ----------------------------------------------------------------

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


def scene_ground(scene: Scene, variant: str = "") -> tuple:
    return scene.grounds.get(variant or "", scene.ground)


def _ground_rows(scene: Scene) -> int:
    return len(scene.ground[0])


def _layers(buf, scene, width, scroll, frame, colors, lights) -> None:
    base = HEIGHT - _ground_rows(scene) - 1
    for layer in scene.layers:
        shift = int(scroll * layer.speed)
        first = -(shift % layer.spacing) - layer.spacing
        for x in range(first, width + layer.spacing, layer.spacing):
            k = (x + shift) // layer.spacing
            if layer.twinkle and ((k * 7 + frame) // layer.twinkle) % 3 == 0:
                continue
            sprite = layer.sprites[k % len(layer.sprites)]
            _stamp(buf, sprite, x, base - layer.y, colors, width)
            if layer.light:
                lights.append((x + len(sprite[0]) // 2, base - layer.y - len(sprite) // 2, layer.light))


def _mover_x(mover: Mover, frame: int, width: int) -> int:
    span = width + 16
    return width - ((frame * mover.speed) % span)


def hero_frame(scene: Scene, phase: str, frame: int) -> Sprite:
    frames = scene.hero.get(phase) or scene.hero.get("idle") or (("",),)
    return frames[frame % len(frames)]


def scene_colors(scene: Scene, variant: str = "") -> dict:
    """The palette with the variant's overrides and auto-derived shadows:
    a lowercase letter the palette lacks is 55 % of its uppercase."""
    from halo_harness.tui.scene_fx import shade
    colors = dict(scene.colors)
    colors.update(scene.variants.get(variant or "", {}))
    for letter, hex_ in list(colors.items()):
        low = letter.lower()
        if letter.isupper() and low not in colors:
            colors[low] = shade(hex_, 0.55)
    return colors


def scene_sky(scene: Scene, variant: str = "") -> tuple:
    sky = scene.skies.get(variant or "", scene.sky)
    if not sky:
        return ()
    return tuple(sky[min(len(sky) - 1, i * len(sky) // HEIGHT)] for i in range(HEIGHT))


def _shots(buf, shot: Shot, origin_x: int, base: int, frame: int, colors, width: int, lights) -> None:
    """Every live launch of `shot` at this frame, deterministically."""
    if shot is None or shot.every <= 0:
        return
    first = max(0, (frame - shot.life) // shot.every)
    for k in range(first, frame // shot.every + 1):
        age = frame - k * shot.every
        if not 0 <= age < shot.life:
            continue
        x = origin_x + shot.dx * shot.speed * age
        sprite = shot.frames[age % len(shot.frames)]
        if x + len(sprite[0]) < 0 or x >= width:
            continue
        _stamp(buf, sprite, x, base - shot.y, colors, width)
        if shot.light:
            lights.append((x + len(sprite[0]) // 2, base - shot.y - len(sprite) // 2, shot.light))


def render_pixels(scene: Scene, width: int, *, phase: str = "idle", frame: int = 0, scroll: int = 0,
                  cue: str = "", variant: str = "", bg: str = "#000000") -> list:
    """The 12 x width colour buffer (hex per pixel; None for a bare sky
    when the scene has no gradient)."""
    from halo_harness.tui.scene_fx import apply_lights
    colors = scene_colors(scene, variant)
    buf = [[None] * width for _ in range(HEIGHT)]
    lights: list = []
    tiles = scene_ground(scene, variant)
    ground = tiles[frame % len(tiles)]
    tile_w = max(1, len(ground[0]))
    start = -(scroll % tile_w)
    for x in range(start, width, tile_w):
        _stamp(buf, ground, x, HEIGHT - 1, colors, width)
    _layers(buf, scene, width, scroll, frame, colors, lights)
    base = HEIGHT - _ground_rows(scene) - 1
    writing = phase in scene.scroll_phases
    if scene.mover is not None and phase in scene.mover.phases:
        mv = scene.mover
        mx = _mover_x(mv, frame, width)
        bob = int(round(mv.bob * math.sin(frame / 2.0))) if mv.bob else 0
        _stamp(buf, mv.frames[frame % len(mv.frames)], mx, base - mv.y - bob, colors, width)
        if mv.shot is not None:
            _shots(buf, mv.shot, mx - 2, base, frame, colors, width, lights)
    hero = hero_frame(scene, phase, frame)
    lift = scene.jump[frame % len(scene.jump)] if (writing and scene.jump) else 0
    _stamp(buf, hero, scene.hero_x, base - lift, colors, width)
    hero_right = scene.hero_x + len(hero[0])
    if writing and scene.flash is not None and frame % scene.flash.every == 0:
        fl = scene.flash
        _stamp(buf, fl.sprite, hero_right + fl.x, base - fl.y - lift, colors, width)
        if fl.light:
            lights.append((hero_right + fl.x + len(fl.sprite[0]) // 2, base - fl.y - lift, fl.light))
    if writing and scene.hero_shot is not None:
        _shots(buf, scene.hero_shot, hero_right, base - lift, frame, colors, width, lights)
    if cue and cue in scene.cues:
        _stamp(buf, scene.cues[cue], hero_right + 2, base - 1, colors, width)
    sky = scene_sky(scene, variant)
    if lights:
        apply_lights(buf, lights, sky, bg)
    if sky:
        for r in range(HEIGHT):
            row = buf[r]
            for c in range(width):
                if row[c] is None:
                    row[c] = sky[r]
    return buf


def render_scene(scene: Scene, width: int, *, phase: str = "idle", frame: int = 0, scroll: int = 0,
                 ascii_mode: bool = False, cue: str = "", bg: str = "#000000", variant: str = "") -> Text:
    """The band for `width` columns: ROWS rows, every row exactly `width`
    cells, bare sky painted `bg` (the theme's background)."""
    from halo_harness.tui.scene_text import pixels_to_text, render_ascii
    width = max(1, int(width or 80))
    if ascii_mode:
        return render_ascii(scene, width, phase=phase, frame=frame, scroll=scroll)
    buf = render_pixels(scene, width, phase=phase, frame=frame, scroll=scroll, cue=cue, variant=variant, bg=bg)
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
