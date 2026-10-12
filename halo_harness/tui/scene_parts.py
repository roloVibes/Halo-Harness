"""halo_harness.tui.scene_parts -- the moving parts of a level (Halo
3.0.2.0): enemies, projectiles and ambient particles, drawn into the pixel
buffer `scene.render_pixels` builds. Split out of tui/scene.py to keep both
files under the house cap; every function here is a pure drawer over
(frame, phase) so captures stay deterministic.
"""

from __future__ import annotations

import math

from halo_harness.tui.scene_model import Mover, Scene, Shot


def _stamp(buf, sprite, x, bottom, colors, width):
    from halo_harness.tui.scene import _stamp as stamp
    stamp(buf, sprite, x, bottom, colors, width)


def _mover_x(mover: Mover, frame: int, width: int) -> int:
    from halo_harness.tui.scene import _mover_x as mover_x
    return mover_x(mover, frame, width)


def hero_frame(scene, phase, frame):
    from halo_harness.tui.scene import hero_frame as hf
    return hf(scene, phase, frame)


def _draw_mover(buf, mv: Mover, phase, frame, base, colors, width, lights) -> None:
    if phase not in mv.phases:
        return
    mx = _mover_x(mv, frame, width)
    bob = int(round(mv.bob * math.sin(frame / 2.0))) if mv.bob else 0
    _stamp(buf, mv.frames[frame % len(mv.frames)], mx, base - mv.y - bob, colors, width)
    if mv.shot is not None:
        _shots(buf, mv.shot, mx - 2, base, frame, colors, width, lights)


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
        y = shot.y + int(round(shot.vy * age - shot.gravity * age * age))
        sprite = shot.frames[age % len(shot.frames)]
        if x + len(sprite[0]) < 0 or x >= width or y < -len(sprite):
            continue
        _stamp(buf, sprite, x, base - y, colors, width)
        if shot.light:
            lights.append((x + len(sprite[0]) // 2, base - y - len(sprite) // 2, shot.light))


def _particles(buf, scene: Scene, phase, frame, scroll, base, colors, width, lights, variant: str = "") -> None:
    from halo_harness.tui.scene_fx import rnd
    for i, p in enumerate(scene.particles):
        if p.phases and phase not in p.phases:
            continue
        if p.variants and (variant or "") not in p.variants:
            continue
        first = max(0, (frame - p.life) // p.every)
        for k in range(first, frame // p.every + 1):
            age = frame - k * p.every
            if not 0 <= age < p.life:
                continue
            r = rnd(k * 31 + i * 97)  # stable per emitter and birth, so captures repeat
            if p.anchor == "hero":
                ox = scene.hero_x + p.x + (r % (p.spread_x + 1))
            else:
                ox = (r % max(1, width + p.spread_x)) - p.spread_x // 2
            oy = p.y + ((r >> 5) % (p.spread_y + 1))
            x = ox + int(round(p.dx * age))
            y = oy + int(round(p.vy * age - p.gravity * age * age))
            sprite = p.frames[age % len(p.frames)]
            if y < 0 or x + len(sprite[0]) < 0 or x >= width:
                continue
            _stamp(buf, sprite, x, base - y, colors, width)
            if p.light:
                lights.append((x, base - y, p.light))




def _draw_combat_enemies(buf, movers, combat: dict, frame: int, base: int, colors, width: int, lights) -> None:
    """Enemies at the positions the fight put them: walking (with the
    mover's bob and shots), or dying (its death frames, or upside down and
    sinking)."""
    from halo_harness.tui.scene_combat import enemy_death_sprite
    for i, (x, mode, t) in (combat.get("enemies") or {}).items():
        if i >= len(movers):
            continue
        mv = movers[i]
        if mode == "walk":
            bob = int(round(mv.bob * math.sin(frame / 2.0))) if mv.bob else 0
            _stamp(buf, mv.frames[frame % len(mv.frames)], x, base - mv.y - bob, colors, width)
            if mv.shot is not None:
                _shots(buf, mv.shot, x - 2, base, frame, colors, width, lights)
        elif mode == "dying":
            sprite, sink = enemy_death_sprite(mv, t)
            _stamp(buf, sprite, x, base - mv.y + sink, colors, width)


def _draw_hero(buf, scene, hero, phase, frame, lift, hero_mode, base, colors, width) -> bool:
    """Draw the hero for its combat mode; True when alive (so shots, flash
    and lamp apply), False while dying or blinking back in."""
    from halo_harness.tui.scene_combat import hero_death_sprite
    mode, t = hero_mode
    if mode == "dying":
        sprite, below = hero_death_sprite(scene, phase, frame, t)
        _stamp(buf, sprite, scene.hero_x, base + below, colors, width)
        return False
    if mode == "respawn":
        if frame % 2 == 0:
            _stamp(buf, hero, scene.hero_x, base - lift, colors, width)
        return False
    _stamp(buf, hero, scene.hero_x, base - lift, colors, width)
    return True
