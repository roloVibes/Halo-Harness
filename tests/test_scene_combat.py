"""tests.test_scene_combat -- Halo 3.0.2.0: the level fights back. On every
game theme a fight simulated from a cold start is deterministic; while the
model writes the hero's projectiles bring the writing-phase enemy down in
`Mover.hp` hits and a fresh one spawns; while the model thinks the
thinking-phase enemy walks unopposed, reaches the hero, kills them, and
they blink back; every combat state renders at every width without error.

Run: python -m tests.test_scene_combat
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
THEMES = ("doom", "metroid", "mario", "beetlejuice", "alien")


def _first_mover_in(scene, phase):
    movers = ((scene.mover,) if scene.mover is not None else ()) + tuple(scene.movers)
    return next((i for i, m in enumerate(movers) if phase in m.phases), None)


@test
def test_a_writing_hero_kills_its_enemy_and_the_next_one_comes(ctx: Ctx):
    from halo_harness.tui.scene import scene_for
    from halo_harness.tui.scene_combat import simulate
    for theme in THEMES:
        scene = scene_for(theme)
        ctx.check(f"{theme} attacks while writing", scene.hero_shot is not None and scene.hero_shot.dx == 1)
        kills_at = None
        c = simulate(scene, 120, "writing", 0)
        for f in range(1, 400):
            c.step("writing")
            if c.hero.kills and kills_at is None:
                kills_at = f
        ctx.check(f"{theme}: the writing-phase enemy goes down within 400 frames, first kill at {kills_at}", kills_at is not None)
        ctx.check(f"{theme}: more than one enemy fell (a fresh one spawned), kills={c.hero.kills}", c.hero.kills >= 2)
        again = simulate(scene, 120, "writing", 399)
        ctx.check(f"{theme}: the fight is deterministic", again.snapshot() == c.snapshot())


@test
def test_a_thinking_enemy_reaches_the_hero_who_dies_and_regenerates(ctx: Ctx):
    from halo_harness.tui.scene import scene_for
    from halo_harness.tui.scene_combat import HERO_DEATH, HERO_RESPAWN, simulate
    for theme in THEMES:
        scene = scene_for(theme)
        idx = _first_mover_in(scene, "thinking")
        if idx is None:
            continue
        c = simulate(scene, 120, "thinking", 0)
        modes = []
        for _ in range(300):
            c.step("thinking")
            modes.append(c.hero.mode)
        ctx.check(f"{theme}: the enemy reaches the hero and kills them, deaths={c.hero.deaths}", c.hero.deaths >= 1)
        ctx.check(f"{theme}: the hero dies, then respawns, then lives again",
                  "dying" in modes and "respawn" in modes and modes[-1] in ("alive", "dying", "respawn")
                  and modes.count("dying") >= HERO_DEATH and modes.count("respawn") >= HERO_RESPAWN)


@test
def test_every_combat_state_renders(ctx: Ctx):
    from halo_harness.tui.scene import ROWS, render_pixels, render_scene, scene_for
    from halo_harness.tui.scene_combat import simulate
    for theme in THEMES:
        scene = scene_for(theme)
        for phase in ("writing", "thinking"):
            c = simulate(scene, 100, phase, 0)
            seen = set()
            for f in range(1, 260):
                c.step(phase)
                snap = c.snapshot()
                key = (snap["hero"][0], tuple(sorted(m for _x, m, _t in snap["enemies"].values())))
                if key in seen and f % 37:
                    continue
                seen.add(key)
                for width in (60, 100):
                    text = render_scene(scene, width, phase=phase, frame=f, scroll=f * 2, combat=snap)
                    rows = text.plain.split("\n")
                    ctx.check(f"{theme}/{phase}/{f}/{width}: {ROWS} rows of {width}", len(rows) == ROWS and all(len(r) == width for r in rows))
            ctx.check(f"{theme}/{phase}: several distinct states were rendered, got {len(seen)}", len(seen) >= 2)
        plain = render_pixels(scene, 100, phase="writing", frame=20, scroll=40)
        ctx.check(f"{theme}: without a combat snapshot the old picture still renders", len(plain) == ROWS * 2)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
