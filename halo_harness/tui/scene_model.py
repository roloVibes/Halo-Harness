"""halo_harness.tui.scene_model -- the data a level band is made of (Halo
3.0.2.0): a sprite is rows of palette letters; Shot, Flash, Layer, Mover
and Scene describe projectiles, muzzle flashes, parallax scenery, the
enemy and the whole scene. Pure data; tui/scene.py renders it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

Sprite = tuple[str, ...]


@dataclass(frozen=True)
class Shot:
    """A projectile: `frames` cycle as it flies `dx` (+1 right, -1 left) at
    `speed` px per frame, launched every `every` frames, living `life`
    frames, `y` px above the ground line; `light` = (hex, radius) glows."""
    frames: tuple[Sprite, ...]
    speed: int = 3
    every: int = 6
    life: int = 24
    y: int = 4
    dx: int = 1
    light: Optional[tuple] = None


@dataclass(frozen=True)
class Flash:
    """A muzzle flash drawn at the hero's right edge every `every` frames
    while writing (frame 0 of the cycle), with its light."""
    sprite: Sprite
    every: int = 4
    x: int = 0
    y: int = 4
    light: Optional[tuple] = None


@dataclass(frozen=True)
class Layer:
    """Scenery repeated along the ground: one of `sprites` every `spacing`
    px (picked by position, so the mix is stable), bottom-aligned `y` px
    above the ground line, scrolling at `speed` times the ground (far
    hills drift slower). `twinkle` > 0 blinks each instance on its own
    rhythm; `light` = (hex, radius) makes every instance a lamp."""
    sprites: tuple[Sprite, ...]
    spacing: int
    speed: float = 1.0
    y: int = 0
    twinkle: int = 0
    light: Optional[tuple] = None


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
    cues: Mapping[str, Sprite] = field(default_factory=dict)
    scroll_phases: frozenset = frozenset({"writing"})
    variants: Mapping[str, Mapping[str, str]] = field(default_factory=dict)  # variant -> colour overrides
    sky: tuple[str, ...] = ()
    skies: Mapping[str, tuple[str, ...]] = field(default_factory=dict)       # variant -> sky
    grounds: Mapping[str, tuple[Sprite, ...]] = field(default_factory=dict)  # variant -> ground frames
    jump: tuple[int, ...] = ()                 # px up, cycled by frame while writing
    flash: Optional[Flash] = None
    hero_shot: Optional[Shot] = None
