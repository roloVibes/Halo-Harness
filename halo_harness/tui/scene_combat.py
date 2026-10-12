"""halo_harness.tui.scene_combat -- the level fights back (Halo 3.0.2.0).

The owner's rule: "if the bad guy in each mode gets to the player, the
player should die and then regenerate. When the player shoots and hits
the bad guy like 3-5 times it dies." `Combat` is that state, stepped once
per band frame and read by `scene.render_pixels`:

- an enemy spawns at the right edge when its phase begins, walks left at
  its speed, and takes a hit from every live hero projectile that reaches
  it (each projectile counts once); at `Mover.hp` hits (four by default)
  it dies -- its own `death` frames, or the generic fall: upside down and
  sinking into the ground -- and a fresh one spawns `RESPAWN` frames later;
- an enemy that reaches the hero kills them: the hero pops up, flips and
  falls through the floor (`HERO_DEATH` frames), then blinks back in place
  (`HERO_RESPAWN` frames, untouchable), and the fight goes on.

Nothing here is random: the same scene, width and phase sequence give the
same fight, so captures and tests repeat byte for byte. `simulate` plays
`frames` steps from a cold start for a still frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

RESPAWN = 28          # frames between an enemy's death and the next one
DEATH_FRAMES = 12     # a generic enemy fall
HERO_DEATH = 14
HERO_RESPAWN = 10
HERO_ARC = (-2, -4, -5, -6, -6, -5, -3, 0, 3, 6, 9, 12, 15, 18)   # px below the ground line per death frame


@dataclass
class EnemyState:
    index: int             # position in (scene.mover, *scene.movers)
    x: int
    hp: int
    mode: str = "walk"     # walk | dying | dead
    t: int = 0
    hits: set = field(default_factory=set)


@dataclass
class HeroState:
    mode: str = "alive"    # alive | dying | respawn
    t: int = 0
    deaths: int = 0
    kills: int = 0


class Combat:
    def __init__(self, scene, width: int) -> None:
        self.scene = scene
        self.width = max(1, int(width or 80))
        self.hero = HeroState()
        self.enemies: dict = {}       # index -> EnemyState
        self.cooldown: dict = {}      # index -> frames until the next spawn
        self.frame = 0

    # -- geometry -----------------------------------------------------------------
    def _movers(self):
        return ((self.scene.mover,) if self.scene.mover is not None else ()) + tuple(self.scene.movers)

    def _hero_span(self, phase: str) -> tuple:
        from halo_harness.tui.scene import hero_frame
        hero = hero_frame(self.scene, phase, self.frame)
        return self.scene.hero_x, self.scene.hero_x + len(hero[0])

    def _shot_positions(self, phase: str, hero_right: int) -> list:
        """(shot index, x) of every live damaging hero projectile this frame."""
        shot = self.scene.hero_shot
        if shot is None or phase not in self.scene.scroll_phases or shot.every <= 0:
            return []
        out = []
        f = self.frame
        first = max(0, (f - shot.life) // shot.every)
        for k in range(first, f // shot.every + 1):
            age = f - k * shot.every
            if 0 <= age < shot.life:
                x = hero_right + shot.dx * shot.speed * age
                out.append((k, x, x + len(shot.frames[age % len(shot.frames)][0])))
        return out

    # -- the step -------------------------------------------------------------------
    def step(self, phase: str, width: Optional[int] = None) -> None:
        if width:
            self.width = max(1, int(width))
        self.frame += 1
        hero_left, hero_right = self._hero_span(phase)
        shots = self._shot_positions(phase, hero_right)
        for i, mv in enumerate(self._movers()):
            if phase not in mv.phases:
                self.enemies.pop(i, None)   # an enemy exists only in its phases (the legacy rule)
                self.cooldown.pop(i, None)
                continue
            e = self.enemies.get(i)
            if e is None:
                if self.cooldown.get(i, 0) > 0:
                    self.cooldown[i] -= 1
                    continue
                e = self.enemies[i] = EnemyState(index=i, x=self.width, hp=max(1, mv.hp))
            if e.mode == "walk":
                e.x -= mv.speed
                w = len(mv.frames[0][0])
                for k, sx0, sx1 in shots:
                    if k not in e.hits and sx1 >= e.x and sx0 <= e.x + w:
                        e.hits.add(k)
                        e.hp -= 1
                if e.hp <= 0:
                    e.mode, e.t = "dying", 0
                    self.hero.kills += 1
                elif self.hero.mode == "alive" and e.x <= hero_right - 2 and e.x + w >= hero_left + 2:
                    self.hero.mode, self.hero.t = "dying", 0
                    self.hero.deaths += 1
                elif e.x + w < 0:
                    self.enemies.pop(i, None)
                    self.cooldown[i] = RESPAWN // 2
            elif e.mode == "dying":
                e.t += 1
                frames = mv.death or ()
                if e.t >= (len(frames) * 3 if frames else DEATH_FRAMES):
                    self.enemies.pop(i, None)
                    self.cooldown[i] = RESPAWN
        h = self.hero
        if h.mode == "dying":
            h.t += 1
            if h.t >= HERO_DEATH:
                h.mode, h.t = "respawn", 0
        elif h.mode == "respawn":
            h.t += 1
            if h.t >= HERO_RESPAWN:
                h.mode, h.t = "alive", 0

    # -- what the renderer reads --------------------------------------------------------
    def snapshot(self) -> dict:
        return {"hero": (self.hero.mode, self.hero.t),
                "enemies": {i: (e.x, e.mode, e.t) for i, e in self.enemies.items()},
                "kills": self.hero.kills, "deaths": self.hero.deaths}


def simulate(scene, width: int, phase: str, frames: int, *, phases: Optional[list] = None) -> Combat:
    """A fight from a cold start: `frames` steps in `phase` (or the per-frame
    `phases` list), for captures and tests."""
    c = Combat(scene, width)
    for i in range(max(0, int(frames))):
        c.step(phases[i] if phases and i < len(phases) else phase)
    return c


def enemy_death_sprite(mv, t: int):
    """The sprite of a dying enemy at death frame `t`, plus how far below
    the ground line to draw it: its own `death` frames, or frame 0 upside
    down sinking one px per frame."""
    if mv.death:
        return mv.death[min(t // 3, len(mv.death) - 1)], 0
    flipped = tuple(reversed(mv.frames[0]))
    return flipped, t


def hero_death_sprite(scene, phase: str, frame: int, t: int):
    """The hero at death frame `t` (flipped, on the arc) -- (sprite, px below ground)."""
    from halo_harness.tui.scene import hero_frame
    sprite = scene.hero.get("dead") or (tuple(reversed(hero_frame(scene, "idle", 0))),)
    return sprite[min(t, len(sprite) - 1)], HERO_ARC[min(t, len(HERO_ARC) - 1)]
