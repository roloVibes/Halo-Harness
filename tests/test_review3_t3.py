"""tests.test_review3_t3 -- pins for the 3.0.2.0 review fix pass, round T-tui:

  * item 78  the model picker reads gym results once and reuses its rows
  * item 162 every level keeps the plain status bar: the same segments and
             values as the default theme under every game theme and variant,
             no door to the panel HUD, and no made-up counters in the band

Run: python -m tests.test_review3_t3
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

GAME_THEMES = ("doom", "metroid", "mario", "beetlejuice", "alien")
PANEL_WORDS = ("AMMO", "HEALTH", "ARMS", "ARMOR", "ENERGY", "MISSILE", "COINS", "SCORE", "LIVES", "WORLD", "TIME")
NOW = 1000.0


def _variants():
    from halo_harness.theme import variants_of
    return [(t, v) for t in GAME_THEMES for v in (variants_of(t) or (None,))]


def _bar_shape(bar) -> "tuple[str, list]":
    content = bar.render()
    plain = getattr(content, "plain", None) or str(content)
    spans = sorted((s.start, s.end) for s in getattr(content, "spans", []))
    return plain, spans


def _load_bar(bar) -> None:
    """Every segment the plain bar can show, at fixed values."""
    bar.apply_status({"model": "or:vendor/strong-model", "permission_mode": "acceptEdits", "effort": "high",
                      "cost_usd": 1.2345, "context_tokens": 50000, "context_limit": 200000, "phase": "thinking",
                      "mcp": {"connected": 2, "total": 3, "tools": 9}})
    bar._phase_started_at = NOW - 18
    bar.set_or_balance("OR $12.40 left", fetched_at=NOW)
    bar.set_agents_running(2)
    bar.set_cwd_branch("/home/kali/proj", "main")
    bar.set_needs_you(2)
    bar.set_pending_permission(True)
    bar.set_background_activity(bg_jobs=1, oldest_elapsed_s=30.0, bg_kinds="bash")
    bar.set_remote_attached(1)
    bar.set_gov_state((2.0, 4.0, 12.0))
    bar.set_offline(True)
    bar.set_statusline_text("custom statusline")


def _frozen_clock():
    from halo_harness.tui.widgets import statusbar as sb_mod
    real = sb_mod.time
    sb_mod.time = SimpleNamespace(monotonic=lambda: NOW, time=real.time)
    return lambda: setattr(sb_mod, "time", real)


def _plain_override():
    """The HUD engine suites force the panel rows on through the test-only
    override and leave it set for the rest of a shared run; a session never
    sets it, so these tests run with it cleared and put it back after."""
    from halo_harness.tui import hud as hud_mod
    saved, hud_mod.STATUS_BAR_OVERRIDE = hud_mod.STATUS_BAR_OVERRIDE, None
    return lambda: setattr(hud_mod, "STATUS_BAR_OVERRIDE", saved)


@test
def test_item162_every_theme_and_variant_renders_the_default_bar(ctx: Ctx):
    from textual.app import App
    from halo_harness.tui.widgets.statusbar import StatusBar

    pairs = _variants()
    names = {t: [v for tt, v in pairs if tt == t] for t in GAME_THEMES}
    ctx.check(f"metroid has its five areas, got {names['metroid']}", len(names["metroid"]) == 5)
    ctx.check(f"mario has its looks, got {names['mario']}", len(names["mario"]) >= 2)
    ctx.check(f"beetlejuice and alien have their places, got {names['beetlejuice']} {names['alien']}",
              set(names["beetlejuice"]) == {"house", "saturn"} and set(names["alien"]) == {"nostromo", "hive"})

    class Host(App):
        def compose(self):
            yield StatusBar(cwd="/home/kali/proj", branch="main")

    async def body():
        app = Host()
        async with app.run_test(size=(400, 10)) as pilot:
            await pilot.pause(0.1)
            bar = app.query_one(StatusBar)
            restore = _frozen_clock()
            undo = _plain_override()
            try:
                _load_bar(bar)
                bar.set_theme("claude-dark")
                base_plain, base_spans = _bar_shape(bar)
                for want in ("strong-model", "50k", "$1.2", "OR $12.40 left", "high", "agents 2", "proj", "main",
                             "thinking 18", "needs you · 2", "permission needed", "bg jobs 1", "gov 2.0 rps",
                             "offline", "custom statusline"):
                    ctx.check(f"the default bar shows {want!r}", want in base_plain)
                for theme, variant in pairs:
                    bar.set_theme(theme, variant)
                    plain, spans = _bar_shape(bar)
                    label = f"{theme}/{variant}"
                    ctx.check(f"{label}: same text as the default bar", plain == base_plain)
                    ctx.check(f"{label}: same segment boundaries (only colour differs)", spans == base_spans)
                    ctx.check(f"{label}: one row, no panel boxes", bar._rows == 1
                              and not any(w in plain for w in PANEL_WORDS))
            finally:
                restore()
                undo()
    asyncio.run(body())


@test
def test_item162_the_live_app_keeps_one_plain_row_under_every_level(ctx: Ctx):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.theme import VARIANT_KEY, set_config_value
    from halo_harness.tui.app import BridgeApp

    async def body():
        app = BridgeApp(FakeController(turns=[]), cwd=str(REPO_DIR))
        async with app.run_test(size=(240, 40)) as pilot:
            await pilot.pause(0.2)
            bar = app.status_bar
            restore = _frozen_clock()
            undo = _plain_override()
            try:
                _load_bar(bar)
                app.apply_theme("claude-dark")
                base_plain, _ = _bar_shape(bar)
                for theme, variant in _variants():
                    if variant:
                        set_config_value(VARIANT_KEY, variant)
                    app.apply_theme(theme)
                    plain, _ = _bar_shape(bar)
                    ctx.check(f"{theme}/{variant}: the app's bar is the default bar on one row",
                              plain == base_plain and bar._rows == 1 and bar.theme_name == theme)
            finally:
                restore()
                set_config_value(VARIANT_KEY, None)
                app.apply_theme("claude-dark")
                undo()
    asyncio.run(body())


@test
def test_item162_nothing_in_a_session_reaches_the_panel_hud(ctx: Ctx):
    from halo_harness.tui import hud as hud_mod
    undo = _plain_override()  # a session never sets the test-only override; the HUD suites do, in a shared run
    try:
        for theme in GAME_THEMES:
            skin = hud_mod.skin_for(theme)
            if skin is not None:
                ctx.check(f"{theme}'s skin keeps the plain bar", skin.status_bar == "plain")
            for variant in [v for t, v in _variants() if t == theme]:
                ctx.check(f"{theme}/{variant}: bar_skin_for is None", hud_mod.bar_skin_for(theme, variant) is None)
    finally:
        undo()
    fresh = hud_mod.HudSkin(name="x", segments=(), strip=(), drop_order=(), faces={},
                            glyphs=None, glyphs_ascii=None, styles={})
    ctx.check("a new skin defaults to the plain bar", fresh.status_bar == "plain")
    writers = []
    for path in (REPO_DIR / "halo_harness").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if re.search(r"STATUS_BAR_OVERRIDE\s*=(?!=)", text) and path.name != "hud.py":
            writers.append(path.name)
        if re.search(r"status_bar\s*=\s*[\"']hud[\"']", text):
            writers.append(path.name + " (a hud skin)")
    ctx.check(f"no production module sets the override or ships a panel skin, got {writers}", writers == [])
    hud_src = (REPO_DIR / "halo_harness" / "tui" / "hud.py").read_text(encoding="utf-8")
    ctx.check("hud.py reads no config key or environment variable",
              "get_config_value" not in hud_src and "os.environ" not in hud_src and "getenv" not in hud_src)


@test
def test_item162_the_level_band_draws_no_counters(ctx: Ctx):
    from halo_harness.tui.scene import render_scene, scene_for
    from halo_harness.tui.scene_combat import simulate
    for theme, variant in _variants():
        scene = scene_for(theme)
        ctx.check(f"{theme} has a level", scene is not None)
        for phase in ("idle", "thinking", "writing", "error", "needs_you"):
            combat = simulate(scene, 100, phase, 40).snapshot()
            for ascii_mode in (False, True):
                text = render_scene(scene, 100, phase=phase, frame=40, scroll=12, ascii_mode=ascii_mode,
                                    cue="agent_done", cue_frame=3, variant=variant or "", combat=combat).plain
                bad = [w for w in PANEL_WORDS if w in text.upper()] + [c for c in text if c.isdigit()]
                ctx.check(f"{theme}/{variant}/{phase}/ascii={ascii_mode}: no counters, got {bad[:5]}", not bad)


@test
def test_item78_picker_reads_gym_once_and_keeps_the_score_suffix(ctx: Ctx):
    from textual.app import App
    from halo_harness import gym as gym_mod
    from halo_harness.config.paths import bridge_home
    from halo_harness.tui.dialogs.model_picker import ModelPicker

    host = Path(bridge_home()) / "gym" / "host1"
    host.mkdir(parents=True, exist_ok=True)
    result = host / "r3t.json"
    result.write_text(json.dumps({"model": "vendor/m-0", "model_ref": "or:vendor/m-0", "finished_at": 1,
                                  "tokens_per_second": 40.0, "tool_call_accuracy": {"score": 0.9},
                                  "edit_success": {"score": 0.8}, "context_recall": {"score": 0.7},
                                  "instruction_adherence": {"score": 0.6}}), encoding="utf-8")
    models = [{"ref": f"or:vendor/m-{i}", "provider": "openrouter", "group": "OpenRouter (or:)",
               "context_tokens": 128000, "price_in_per_m": 1.0, "price_out_per_m": 2.0} for i in range(300)]
    reads = []
    real_iter = gym_mod.iter_results
    gym_mod.iter_results = lambda state_dir: reads.append(1) or real_iter(state_dir)

    async def body():
        app = App()
        async with app.run_test(size=(140, 40)) as pilot:
            picker = ModelPicker(models)
            app.push_screen(picker)
            await pilot.pause(0.3)
            for query in ("m", "m-", "m-1", ""):
                picker._refresh_list(query)
            ol = picker.query_one("#model-list")
            first = str(ol.get_option("or:vendor/m-0").prompt)
            ctx.check(f"gym results were read once for five refreshes, got {len(reads)}", len(reads) == 1)
            ctx.check(f"the score suffix still shows, got {first!r}", "gym" in first)
            ctx.check(f"every row is listed, got {ol.option_count}", ol.option_count == 301)
    try:
        asyncio.run(body())
    finally:
        gym_mod.iter_results = real_iter
        result.unlink()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
