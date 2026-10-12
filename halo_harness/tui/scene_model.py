"""halo_harness.tui.scene_model -- the data a level band is made of (Halo
3.0.2.0, third generation): a sprite is rows of palette letters; Shot,
Flash, Layer, Particle, Mover and Scene describe projectiles, muzzle
flashes, parallax scenery, ambient particles, the enemy and the whole
scene. Pure data; tui/scene.py renders it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

Sprite = tuple[str, ...]


@dataclass(frozen=True)
class Shot:
    """A projectile: `frames` cycle as it flies `dx` (+1 right, -1 left) at
    `speed` px per frame, launched every `every` frames, living `life`
    frames, starting `y` px above the ground line; `vy` px/frame upward
    and `gravity` px/frame^2 bend the path (a shell casing arcs); `light`
    = (hex, radius) glows."""
    frames: tuple[Sprite, ...]
    speed: int = 3
    every: int = 6
    life: int = 24
    y: int = 4
    dx: int = 1
    vy: float = 0.0
    gravity: float = 0.0
    light: Optional[tuple] = None


@dataclass(frozen=True)
class Flash:
    """A muzzle flash drawn at the hero's right edge every `every` frames
    while writing; `frames` cycle per shot, with its light."""
    frames: tuple[Sprite, ...]
    every: int = 4
    x: int = 0
    y: int = 4
    light: Optional[tuple] = None


@dataclass(frozen=True)
class Layer:
    """Scenery repeated along the ground: one of `sprites` every `spacing`
    px (picked by position, so the mix is stable; `animate` > 0 cycles
    the sprites by time instead, every `animate` frames), bottom-aligned
    `y` px above the ground line, scrolling at `speed` times the ground
    (far hills drift slower). `twinkle` > 0 blinks each instance on its
    own rhythm; `light` = (hex, radius) makes every instance a lamp and
    `flicker` > 0 makes that lamp breathe."""
    sprites: tuple[Sprite, ...]
    spacing: int
    speed: float = 1.0
    y: int = 0
    twinkle: int = 0
    light: Optional[tuple] = None
    animate: int = 0
    flicker: int = 0


@dataclass(frozen=True)
class Particle:
    """An ambient emitter: every `every` frames one particle is born and
    lives `life` frames cycling `frames`. `anchor` "hero" births it at
    the hero's feet (+`x`, `y` above the ground), "world" somewhere across
    the band (`y` above the ground, `spread_y` random extra height); it
    drifts `dx` px/frame, rises `vy` px/frame and falls under `gravity`.
    Emits only in `phases` (empty = always)."""
    frames: tuple[Sprite, ...]
    every: int = 6
    life: int = 16
    anchor: str = "world"
    x: int = 0
    y: int = 0
    spread_x: int = 0
    spread_y: int = 0
    dx: float = 0.0
    vy: float = 0.0
    gravity: float = 0.0
    phases: frozenset = frozenset()
    light: Optional[tuple] = None
    variants: frozenset = frozenset()   # emits only under these variants (empty = all)


@dataclass(frozen=True)
class Mover:
    """The enemy: crosses right to left at `speed` px per frame while the
    phase is one of `phases`, cycling `frames`, bobbing `bob` px on a sine,
    firing `shot` to the left."""
    frames: tuple[Sprite, ...]
    phases: frozenset
    speed: int = 2
    y: int = 0
    bob: int = 0
    shot: Optional[Shot] = None
    hp: int = 4                             # hero projectile hits it takes (scene_combat)
    death: tuple = ()                       # its own death frames (3 band frames each); empty = fall over and sink


@dataclass(frozen=True)
class Scene:
    name: str
    colors: Mapping[str, str]
    ground: tuple[Sprite, ...]                 # animated tile: frames of equal width
    hero: Mapping[str, tuple[Sprite, ...]]     # phase -> frames; "idle" is the fallback
    ascii: Mapping[str, tuple[str, ...]]       # "hero", "mover", "tile": rows; "ground": one char
    hero_x: int = 10
    layers: tuple[Layer, ...] = ()
    mover: Optional[Mover] = None
    movers: tuple[Mover, ...] = ()             # more enemies (each with its own phases)
    cues: Mapping[str, tuple[Sprite, ...]] = field(default_factory=dict)   # event -> animation frames
    cue_rise: Mapping[str, tuple[int, ...]] = field(default_factory=dict)  # event -> px up per cue frame
    scroll_phases: frozenset = frozenset({"writing"})
    variants: Mapping[str, Mapping[str, str]] = field(default_factory=dict)  # variant -> colour overrides
    sky: tuple[str, ...] = ()
    skies: Mapping[str, tuple[str, ...]] = field(default_factory=dict)       # variant -> sky
    grounds: Mapping[str, tuple[Sprite, ...]] = field(default_factory=dict)  # variant -> ground frames
    jump: tuple[int, ...] = ()                 # px up, cycled by frame while writing
    flash: Optional[Flash] = None
    hero_shot: Optional[Shot] = None
    particles: tuple[Particle, ...] = ()
    hero_light: Optional[tuple] = None         # (hex, radius) carried by the hero (a helmet lamp)
    hero_light_phases: frozenset = frozenset()
    hero_eject: Optional[Shot] = None          # a harmless projectile (the shell casing); hero_shot does the damage
