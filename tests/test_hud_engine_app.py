"""tests.test_hud_engine_app -- the game-HUD status bar inside a real
BridgeApp (Halo 2.0.8 theme pack, round 1): row count, face states through
the StatusBar setters and dispatch, leaving DOOM, the compact line. The pure
engine tests live in tests/test_hud_engine.py.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

test, TESTS = new_registry()


# ---- pilots ------------------------------------------------------------------

def _plain(bar) -> str:
    return str(bar.render())


def _app(theme: str = "doom"):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project", theme_name=theme)


@test
def test_doom_statusbar_in_a_real_app_is_three_rows_and_follows_the_phase(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.1)
            bar = app.status_bar
            bar.hud_ascii = False
            await pilot.pause(0.05)
            ctx.check(f"3 rows tall under doom, got {bar.size.height}", bar.size.height == 3)
            ctx.check("the app carries the heavy-border class", app.has_class("hud-heavy"))
            bar.apply_status({"model": "or:demo/atlas-pro", "context_tokens": 300_000, "context_limit": 1_000_000,
                              "cost_usd": 0.0123, "mcp": {"connected": 3, "total": 3, "tools": 41}})
            bar.set_cwd_branch("~/project", "main")
            plain = _plain(bar)
            for needle in ("AMMO", "HEALTH", "ARMS", "ARMOR", "700k left", "70%", "41 tools", "$0.0123", "~/project (main)"):
                ctx.check(f"HUD shows {needle!r}", needle in plain)
            ctx.check("idle face", "▐o_o▌" in plain)
            bar.start_phase_clock("thinking")
            ctx.check("thinking face", "▐'_'▌" in _plain(bar))
            bar.set_phase_word("writing")
            ctx.check("writing face", "▐^o^▌" in _plain(bar))
            bar.set_error(True)
            ctx.check("error face", "▐x_x▌" in _plain(bar))
            bar.set_pending_permission(True)
            ctx.check("needs-you outranks error", "▐O!O▌" in _plain(bar))
            bar.set_pending_permission(False)
            bar.start_phase_clock("thinking")
            ctx.check("the next call clears the error face", "x_x" not in _plain(bar))
            bar.go_idle()
            bar.set_error(True)
            bar.go_idle()
            ctx.check("an error survives the turn_done that follows it", "▐x_x▌" in _plain(bar))
    asyncio.run(body())


@test
def test_leaving_doom_restores_the_one_row_default_bar(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.1)
            app.apply_theme("claude-dark")
            await pilot.pause(0.1)
            ctx.check(f"1 row again, got {app.status_bar.size.height}", app.status_bar.size.height == 1)
            ctx.check("heavy-border class removed", not app.has_class("hud-heavy"))
            ctx.check("no HUD captions left", "AMMO" not in _plain(app.status_bar))
            app.apply_theme("mario")
            await pilot.pause(0.1)
            ctx.check("mario uses the default layout until round 3 (1 row)", app.status_bar.size.height == 1)
            ctx.check("mario default layout still shows the context field", "ctx" in _plain(app.status_bar))
    asyncio.run(body())


@test
def test_narrow_terminal_collapses_to_the_compact_line_and_back(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(40, 20)) as pilot:
            await pilot.pause(0.1)
            app.status_bar.hud_ascii = False
            app.status_bar.apply_status({"model": "or:demo/atlas-pro", "context_tokens": 1, "context_limit": 10, "cost_usd": 0.5})
            await pilot.pause(0.1)
            ctx.check(f"1 compact row at 40 columns, got {app.status_bar.size.height}", app.status_bar.size.height == 1)
            await pilot.resize_terminal(100, 20)
            await pilot.pause(0.1)
            app.status_bar._refresh_display()
            await pilot.pause(0.1)
            ctx.check(f"3 rows again at 100 columns, got {app.status_bar.size.height}", app.status_bar.size.height == 3)
    asyncio.run(body())


@test
def test_error_event_sets_the_face_through_dispatch(ctx: Ctx):
    from halo_harness import events as ev
    from halo_harness.tui.dispatch import apply_event

    async def body():
        app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.1)
            app.status_bar.hud_ascii = False
            await apply_event(app, ev.Event("error", {"message": "boom"}, turn=1))
            await pilot.pause(0.05)
            ctx.check("a main-session error event shows the error face", "▐x_x▌" in _plain(app.status_bar))
            t0 = time.monotonic()
            await apply_event(app, ev.Event("phase", {"state": "request_sent"}, turn=2))
            ctx.check("the next request clears it", "x_x" not in _plain(app.status_bar))
            ctx.check("fast", time.monotonic() - t0 < 5)
    asyncio.run(body())


# ---- the slot vocabulary against the real StatusBar --------------------------

@test
def test_statusbar_fields_cover_everything_the_default_layout_shows(ctx: Ctx):
    from halo_harness.tui.hud_fields import build_fields

    async def build():
        app = _app("claude-dark")
        async with app.run_test(size=(100, 20)) as pilot:
            await pilot.pause(0.05)
            bar = app.status_bar
            bar.cwd, bar.branch = "~/project", "main"
            bar.model, bar.context_tokens, bar.context_limit, bar.context_pct = "or:demo/atlas-pro", 200_000, 1_000_000, 20.0
            bar.cost_usd, bar.effort, bar.mcp_connected, bar.mcp_total, bar.tools_loaded = 0.5, "high", 2, 3, 12
            bar.statusline_text = "\x1b[31mred\x1b[0m"
            bar.set_provider_balance("openrouter", "OR $12.40 left")
            s = dict(mcp_str="MCP 2/3", cost_str="$0.5000", or_balance_str="OR $12.40 left",
                     loc_str="~/project (main)", cwd_short="project (main)", mode_str="auto",
                     effort_str="high", needs_you_str="needs you · 2", agents_str="agents 1", offline_str="offline",
                     gov_str="gov 2.0 rps", new_str="↓ 3 new", hang_str="⏠ hang-watch 4 s",
                     throughput_str="41 tok/s", permission_str="permission needed: 1 yes", bg_jobs_str="bg jobs 2",
                     oldest_str="oldest 9 s", spinner_str="⠋ writing 3 s · ↓12", elapsed_str="3 s")
            return build_fields(bar, s)
    fields = asyncio.run(build())
    shown_by_default = ("model", "tokens", "context", "tools", "mcp", "cost", "providers", "cwd", "branch", "mode",
                        "effort", "phase", "elapsed", "needs_you", "permission", "agents", "bg", "hang", "offline",
                        "gov", "new", "throughput", "statusline")
    missing = [k for k in shown_by_default if k not in fields or not fields[k].long]
    ctx.check(f"every status-bar value has a slot, missing: {missing}", not missing)
    ctx.check("the custom status line arrives as plain text", fields["statusline"].long == "red")
    ctx.check("context slot is REMAINING percent", fields["context"].long == "80%" and abs(fields["context"].frac - 0.8) < 1e-9)
    ctx.check("tokens slot is remaining tokens", fields["tokens"].long.startswith("800k"))
    ctx.check("cost carries the balance in its long form", "OR $12.40 left" in fields["cost"].long)
    ctx.check("providers include the active prefix", fields["providers"].long.split()[0] == "or")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
