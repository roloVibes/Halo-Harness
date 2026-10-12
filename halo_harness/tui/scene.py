"""halo_harness.tui.scene -- the level-band engine (Halo 2.0.11 round A3;
3.0.2.0 "the levels, third generation").

A game theme declares a `Scene`: a strip above the prompt that plays like a
16-bit side-scroller. Eight terminal rows hold sixteen pixel rows (two per
cell through the half-block glyphs); one pixel per column. A sprite is a
tuple of rows of palette letters (`.` is transparent). Uppercase letters
are the palette, and a lowercase letter that the palette does not name is
the darker shade of its uppercase, so art carries its own shadows; every
hero wears a dark outline so it reads at a glance over busy scenery.

What a scene can have, all pure data (the themes live in scene_mario.py,
scene_metroid.py and scene_doom.py; `scene_fx.py` holds shading, lights
and the pseudo-random; `scene_text.py` turns pixels into Rich text):

- `sky`: a vertical gradient (one hex per pixel row) behind everything;
- `ground`: an animated tile (frames), bottom-aligned;
- `layers`: parallax scenery at its own speed and height, optionally
  blinking (`twinkle`), cycling (`animate`) or casting light (`light`,
  breathing with `flicker`);
- `particles`: ambient emitters (dust at the hero's feet, embers, spores,
  drips) with drift, rise and gravity;
- `hero`: frames per phase, a `jump` table while writing, a `flash`
  (muzzle, every N frames, with a light), a `hero_shot` (a projectile
  fired to the right while writing) and a `hero_light` (a helmet lamp);
- `mover`/`movers`: enemies crossing right to left in their phases, with a
  sine `bob` and their own `shot` fired to the left;
- `cues`: a short animation beside the hero (agent done, job done), rising
  by `cue_rise`.

`render_pixels` returns the 16 x width colour buffer; `render_scene` the
Rich Text. Both are pure functions of (phase, frame, scroll, cue,
cue_frame, variant), so captures are deterministic. All art is original:
silhouettes in the spirit of the 16-bit era, nothing copied from any game.
"""

from __future__ import annotations

from typing import Optional

from rich.text import Text

ROWS = 8
HEIGHT = ROWS * 2
PHASES = ("idle", "thinking", "writing", "error", "needs_you")

from halo_harness.tui.scene_model import Flash, Layer, Mover, Particle, Scene, Shot, Sprite  # noqa: F401,E402


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
            idx = (k + frame // layer.animate) if layer.animate else k
            sprite = layer.sprites[idx % len(layer.sprites)]
            _stamp(buf, sprite, x, base - layer.y, colors, width)
            if layer.light:
                color, radius = layer.light
                if layer.flicker:
                    radius -= ((frame // layer.flicker) + k) % 2
                lights.append((x + len(sprite[0]) // 2, base - layer.y - len(sprite) // 2, (color, radius)))


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


def render_pixels(scene: Scene, width: int, *, phase: str = "idle", frame: int = 0, scroll: int = 0,
                  cue: str = "", cue_frame: int = 0, variant: str = "", bg: str = "#000000",
                  combat: Optional[dict] = None) -> list:
    """The 16 x width colour buffer (hex per pixel; None for a bare sky
    when the scene has no gradient). `combat` is a `scene_combat.Combat`
    snapshot: enemies at their fought positions (walking, dying) and the
    hero alive, dying or blinking back; without it the enemies simply
    cross on the frame counter (the pre-combat picture, still used by the
    placement tests)."""
    from halo_harness.tui.scene_fx import apply_lights
    from halo_harness.tui.scene_parts import _draw_combat_enemies, _draw_hero, _draw_mover, _particles, _shots
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
    movers = ((scene.mover,) if scene.mover is not None else ()) + tuple(scene.movers)
    if combat is None:
        for mv in movers:
            _draw_mover(buf, mv, phase, frame, base, colors, width, lights)
    else:
        _draw_combat_enemies(buf, movers, combat, frame, base, colors, width, lights)
    _particles(buf, scene, phase, frame, scroll, base, colors, width, lights, variant)
    hero = hero_frame(scene, phase, frame)
    lift = scene.jump[frame % len(scene.jump)] if (writing and scene.jump) else 0
    hero_mode = (combat or {}).get("hero", ("alive", 0))
    alive = _draw_hero(buf, scene, hero, phase, frame, lift, hero_mode, base, colors, width)
    hero_right = scene.hero_x + len(hero[0])
    if not alive:
        writing = False   # no shooting, no flash while dead or blinking back
    if scene.hero_light and alive and (not scene.hero_light_phases or phase in scene.hero_light_phases):
        lights.append((scene.hero_x + len(hero[0]) // 2, base - lift - len(hero) + 3, scene.hero_light))
    if writing and scene.hero_eject is not None:
        _shots(buf, scene.hero_eject, hero_right, base - lift, frame, colors, width, lights)
    if writing and scene.flash is not None and frame % scene.flash.every == 0:
        fl = scene.flash
        sprite = fl.frames[(frame // fl.every) % len(fl.frames)]
        _stamp(buf, sprite, hero_right + fl.x, base - fl.y - lift, colors, width)
        if fl.light:
            lights.append((hero_right + fl.x + len(sprite[0]) // 2, base - fl.y - lift, fl.light))
    if writing and scene.hero_shot is not None:
        _shots(buf, scene.hero_shot, hero_right, base - lift, frame, colors, width, lights)
    if cue and cue in scene.cues:
        frames = scene.cues[cue]
        rise = scene.cue_rise.get(cue, (0,))
        sprite = frames[min(cue_frame, len(frames) - 1)] if len(frames) > 1 and cue_frame < len(frames) else frames[cue_frame % len(frames)]
        _stamp(buf, sprite, hero_right + 2, base - 1 - rise[min(cue_frame, len(rise) - 1)], colors, width)
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
                 ascii_mode: bool = False, cue: str = "", cue_frame: int = 0, bg: str = "#000000",
                 variant: str = "", combat: Optional[dict] = None) -> Text:
    """The band for `width` columns: ROWS rows, every row exactly `width`
    cells, bare sky painted `bg` (the theme's background)."""
    from halo_harness.tui.scene_text import pixels_to_text, render_ascii
    width = max(1, int(width or 80))
    if ascii_mode:
        return render_ascii(scene, width, phase=phase, frame=frame, scroll=scroll)
    buf = render_pixels(scene, width, phase=phase, frame=frame, scroll=scroll, cue=cue, cue_frame=cue_frame,
                        variant=variant, bg=bg, combat=combat)
    return pixels_to_text(buf, bg)


_SCENES: dict = {}


def register_scene(scene: Scene) -> Scene:
    _SCENES[scene.name] = scene
    return scene


def scene_for(theme: str) -> Optional[Scene]:
    """The scene of game theme `theme`, importing its module on first use
    (the same lazy pattern as `hud.skin_for`); None for a theme without one."""
    if theme and theme not in _SCENES and theme.isidentifier():
        import importlib
        try:
            importlib.import_module(f"halo_harness.tui.scene_{theme}")
        except ImportError:
            _SCENES[theme] = None  # a theme without a level; remembered so the import is tried once
    return _SCENES.get(theme)
