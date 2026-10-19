"""tests.test_scene -- the level-band engine (Halo 2.0.11 round A3): every
game theme's scene renders at 60/80/120/200 columns in every phase and in
ASCII mode, each row exactly the width asked for, deterministic in
(frame, scroll), the hero on the ground, the mover only in its phases,
the cue sprite beside the hero, variant colours applied; the band widget
appears under a game theme at 120x40, yields below 24 rows, and `/level`
hides and restores it.
"""

from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
THEMES = ("doom", "metroid", "mario", "beetlejuice", "alien")


def _rows(text) -> list:
    return text.plain.split("\n")


@test
def test_every_scene_renders_every_phase_at_every_width(ctx: Ctx):
    from rich.cells import cell_len
    from halo_harness.tui.scene import PHASES, ROWS, render_scene, scene_for
    for theme in THEMES:
        scene = scene_for(theme)
        ctx.check(f"{theme} has a scene", scene is not None)
        for width in (60, 80, 120, 200):
            for phase in PHASES:
                for ascii_mode in (False, True):
                    text = render_scene(scene, width, phase=phase, frame=7, scroll=13, ascii_mode=ascii_mode,
                                        bg="#101010", cue="agent_done")
                    rows = _rows(text)
                    ctx.check(f"{theme}/{phase}/{width}/ascii={ascii_mode}: {ROWS} rows", len(rows) == ROWS)
                    ctx.check(f"{theme}/{phase}/{width}/ascii={ascii_mode}: every row is {width} cells",
                              all(cell_len(r) == width for r in rows))
                    if not ascii_mode:
                        ctx.check(f"{theme}/{phase}/{width}: block glyphs only",
                                  set(text.plain) <= set("▀▄█ \n"))


@test
def test_render_is_deterministic_and_scroll_moves_the_scenery(ctx: Ctx):
    from halo_harness.tui.scene import render_pixels, render_scene, scene_for
    scene = scene_for("mario")
    a = render_scene(scene, 100, phase="writing", frame=4, scroll=10, bg="#000000")
    b = render_scene(scene, 100, phase="writing", frame=4, scroll=10, bg="#000000")
    ctx.check("same inputs, same output", a.plain == b.plain and a.spans == b.spans)
    p0 = render_pixels(scene, 100, phase="idle", frame=0, scroll=0)
    p1 = render_pixels(scene, 100, phase="idle", frame=0, scroll=6)
    ctx.check("scrolling changes the scenery", p0 != p1)
    ctx.check("the ground row is fully painted", all(px is not None for px in p0[-1]))


@test
def test_hero_mover_and_cue_placement(ctx: Ctx):
    from halo_harness.tui.scene import HEIGHT, hero_frame, render_pixels, scene_for, scene_colors
    for theme in THEMES:
        scene = scene_for(theme)
        colors = scene_colors(scene)
        hero = hero_frame(scene, "idle", 0)
        from dataclasses import replace
        unlit = replace(scene, layers=(), particles=(), hero_light=None)  # 3.0.2.0: lamps may tint the hero
        buf = render_pixels(unlit, 120, phase="idle", frame=0, scroll=0)
        base = HEIGHT - len(scene.ground[0]) - 1
        top = base - len(hero) + 1
        painted = [(r, c) for r, row in enumerate(hero) for c, ch in enumerate(row) if ch != "."]
        ctx.check(f"{theme}: the hero stands on the ground at x={scene.hero_x}",
                  all(buf[top + r][scene.hero_x + c] == colors[hero[r][c]] for r, c in painted))
        for phase in ("idle", "writing", "thinking"):
            with_mover = render_pixels(scene, 120, phase=phase, frame=5, scroll=0)
            without = render_pixels(scene, 120, phase=phase, frame=5, scroll=0, variant="")
            ctx.check(f"{theme}/{phase}: a render is stable", with_mover == without)
        mv = scene.mover
        on = render_pixels(scene, 120, phase=next(iter(mv.phases)), frame=3, scroll=0)
        off_phase = "idle"
        off = render_pixels(scene, 120, phase=off_phase, frame=3, scroll=0)
        ctx.check(f"{theme}: the mover shows only in its phases ({sorted(mv.phases)})", on != off)
        cue = render_pixels(scene, 120, phase="idle", frame=0, scroll=0, cue="agent_done")
        plain = render_pixels(scene, 120, phase="idle", frame=0, scroll=0)
        ctx.check(f"{theme}: the agent_done cue draws beside the hero", cue != plain)
        ctx.check(f"{theme}: an unknown cue draws nothing",
                  render_pixels(scene, 120, phase="idle", frame=0, scroll=0, cue="nope") == plain)


@test
def test_variants_recolour_and_unknown_theme_has_no_scene(ctx: Ctx):
    from halo_harness.tui.scene import render_pixels, scene_for
    metroid = scene_for("metroid")
    crateria = render_pixels(metroid, 80, phase="idle", variant="crateria")
    norfair = render_pixels(metroid, 80, phase="idle", variant="norfair")
    ctx.check("Norfair's lava ground differs from Crateria's rock", crateria[-1] != norfair[-1])
    mario = scene_for("mario")
    ctx.check("a Mario variant renders", render_pixels(mario, 80, phase="idle", variant="world") is not None)
    ctx.check("a non-game theme has no scene", scene_for("claude-dark") is None)


def _app(theme: str, size):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project", theme_name=theme), size


@test
def test_band_widget_shows_yields_and_toggles(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    async def body():
        app, size = _app("mario", (120, 40))
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.1)
            band = app.scene_band
            ctx.check("the band exists under the mario theme", band is not None and band.scene is not None)
            ctx.check("the band is shown at 120x40", band.display is True)
            ctx.check("the band sits above the prompt row in the bottom dock",
                      [w.id for w in app.query_one("#bottom-dock").children][:2] == ["scene-band", "prompt-row"])
            app.status_bar.set_phase_word("writing")
            before = band.frame
            band._tick()
            ctx.check("a tick advances the frame and scrolls while writing", band.frame == before + 1 and band.scroll > 0)
            ctx.check("a cue the scene knows is accepted", band.fire_cue("agent_done") is True)
            ctx.check("a cue the scene lacks is refused", band.fire_cue("nothing") is False)
            await handle_slash(app, "level", "off")
            await pilot.pause(0.05)
            ctx.check("/level off hides the band", band.display is False)
            await handle_slash(app, "level", "")
            await pilot.pause(0.05)
            ctx.check("bare /level toggles it back", band.display is True)
            await handle_slash(app, "theme", "claude-dark")
            await pilot.pause(0.05)
            ctx.check("a non-game theme hides the band", band.display is False)
        app, size = _app("doom", (120, 22))
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.1)
            ctx.check("at 120x22 the band yields the rows", app.scene_band.display is False)

    asyncio.run(body())


@test
def test_band_returns_the_moment_the_rows_allow_and_repaints_in_place(ctx: Ctx):
    """3.1.3.0: the app's own Resize brings a hidden band back (no idle tick
    needed), 24 rows are enough, and a frame never asks for a screen layout."""
    from tests.helpers.layout_watch import watch_own_layout_requests

    async def body():
        app, size = _app("doom", (120, 40))
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.1)
            band = app.scene_band
            band.pause()  # no idle tick may rescue it: the app's Resize has to
            ctx.check("shown at 120x40", band.display is True)
            await pilot.resize_terminal(120, 20)
            await pilot.pause(0.1)
            ctx.check("hidden at 20 rows", band.display is False)
            await pilot.resize_terminal(120, 24)
            await pilot.pause(0.15)
            ctx.check("back at 24 rows, with the timer stopped", band.display is True)
            lines = str(band.render()).split("\n")
            ctx.check(f"the frame is eight rows at the new width, got {len(lines)}x{len(lines[0]) if lines else 0}",
                      len(lines) == 8 and all(len(line) == 120 for line in lines))
            with watch_own_layout_requests(band) as asked:
                band._tick()
                await pilot.pause(0.1)
            ctx.check(f"a band frame makes no layout request of its own, got {asked}", not asked)

    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="scene tests"))
