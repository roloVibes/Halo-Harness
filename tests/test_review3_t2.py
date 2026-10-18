"""tests.test_review3_t2 -- pins for the 3.0.2.0 review fix pass, round T-tui
(dialogs and the wizard):

  * item 76  a corrupt studio.json port reads as "no Studio", never a crash
  * item 77  Back from a step the Summary jumped to returns the index too
  * item 79  the Studio URL stays on screen; a newer hint is never cleared early
  * item 146 re-picking a role's model keeps its escalation override
  * item 147 Org mode's pause/resume runs off the event loop, with short timeouts

Item 78 (picker speed) and item 162 (game status bar) are in _t3; 148/149 in _t4.

Run: python -m tests.test_review3_t2
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import json
import sys
import time
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _text(widget) -> str:
    return str(widget.renderable) if hasattr(widget, "renderable") else str(widget.render())


def _host():
    from textual.app import App
    return App()


@test
def test_item76_corrupt_port_and_a_raising_launch_never_end_the_wizard(ctx: Ctx):
    from halo_harness.providers.config import default_state_dir
    from halo_harness.studio import launch as launch_mod
    from halo_harness.studio.server import studio_info_path
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState
    state = Path(default_state_dir())
    state.mkdir(parents=True, exist_ok=True)
    info = studio_info_path(state)
    info.write_text(json.dumps({"pid": 1, "port": "abc"}), encoding="utf-8")
    try:
        ctx.check("read_info treats a non-numeric port as no Studio", launch_mod.read_info(state) is None)
        ctx.check("existing_url answers '' instead of raising", launch_mod.existing_url(state, "roles") == "")
    finally:
        info.unlink()
    ctx.check("port_answers on garbage is False", launch_mod.port_answers("abc") is False)

    async def body():
        real = launch_mod.launch_detached

        def boom(*_a, **_kw):
            raise ValueError("invalid literal for int()")
        launch_mod.launch_detached = boom
        try:
            app = InitWizardApp(WizardState(cwd=REPO_DIR, step_keys=("team",), no_live=True))
            async with app.run_test(size=(110, 40)) as pilot:
                await pilot.pause(0.2)
                app.screen.action_open_studio()
                await pilot.pause(0.5)
                hint = _text(app.screen.query_one("#wiz-team-lineup-hint"))
                ctx.check("the wizard is still running", app.is_running and app.return_code is None)
                ctx.check(f"it says Studio did not start, got {hint!r}", "did not start" in hint)
        finally:
            launch_mod.launch_detached = real
    asyncio.run(body())


@test
def test_item77_back_from_a_jumped_step_lands_on_the_summary_index(ctx: Ctx):
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, SummaryStep, WizardState, advance, go_back

    async def body():
        state = WizardState(cwd=REPO_DIR, step_keys=("theme", "orgs", "summary"), no_live=True)
        app = InitWizardApp(state)
        async with app.run_test(size=(110, 40)) as pilot:
            await pilot.pause(0.2)
            advance(app, state)
            advance(app, state)
            await pilot.pause(0.3)
            summary = app.screen
            ctx.check("on the Summary", isinstance(summary, SummaryStep) and state.index == 2)
            for key in ("orgs", "theme"):
                summary._jump_to(key)
                await pilot.pause(0.2)
                go_back(app, state)
                await pilot.pause(0.2)
                ctx.check(f"Back from {key} is the same Summary, index {state.index}",
                          app.screen is summary and state.index == 2)
            finished = []
            state.on_finish = lambda _app: finished.append(True)
            advance(app, state)
            await pilot.pause(0.1)
            ctx.check("Finish finishes instead of re-opening a step", finished == [True])
    asyncio.run(body())


@test
def test_item79_studio_url_stays_and_older_timers_never_clear_newer_text(ctx: Ctx):
    from halo_harness.studio import launch as launch_mod
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    def slow_url(mode, **_kw):
        time.sleep(0.4)
        return f"http://127.0.0.1:43001/?mode={mode}#t=tok"

    async def body():
        real = launch_mod.launch_detached
        launch_mod.launch_detached = slow_url
        try:
            for key, selector in (("team", "#wiz-team-lineup-hint"), ("orgs", "#wiz-orgs-studio-url")):
                app = InitWizardApp(WizardState(cwd=REPO_DIR, step_keys=(key,), no_live=True))
                async with app.run_test(size=(110, 44)) as pilot:
                    await pilot.pause(0.2)
                    app.screen.action_open_studio()
                    await pilot.pause(3.2)
                    shown = _text(app.screen.query_one(selector))
                    ctx.check(f"{key}: the URL is still shown after 3 s, got {shown!r}", "#t=tok" in shown)
        finally:
            launch_mod.launch_detached = real
    asyncio.run(body())


@test
def test_item146_new_model_keeps_the_escalation_override(ctx: Ctx):
    from textual.widgets import Input
    from halo_harness.tui.dialogs.roles_editor import RolesEditor

    async def body():
        app = _host()
        async with app.run_test(size=(110, 40)) as pilot:
            ed = RolesEditor("t", {"reviewer": {"model": "or:a/b", "effort": "high", "escalation": False}}, [])
            app.push_screen(ed)
            await pilot.pause(0.2)
            ed._pending_role, ed._pending_model, ed._pending_agent = "reviewer", "or:c/d", None
            ok = ed._commit_pending("high", ed.query_one("#roles-effort-input", Input))
            ctx.check(f"committed, got {ed.roles['reviewer']}", ok and ed.roles["reviewer"] ==
                      {"model": "or:c/d", "escalation": False, "effort": "high"})
            ed.roles["plain"] = "or:x/y"
            ed._pending_role, ed._pending_model, ed._pending_agent = "plain", "or:z/w", None
            ed._commit_pending("", ed.query_one("#roles-effort-input", Input))
            ctx.check(f"a role with nothing extra stays a bare string, got {ed.roles['plain']!r}",
                      ed.roles["plain"] == "or:z/w")
    asyncio.run(body())


@test
def test_item147_org_mode_switch_never_blocks_the_wizard(ctx: Ctx):
    from textual.widgets import Switch
    from halo_harness.paperclip import mode as mode_mod
    from halo_harness.paperclip.client import Paperclip
    from halo_harness.theme import get_config_value, set_config_value
    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    seen = []
    client = Paperclip("http://127.0.0.1:9", timeout=30.0)
    client.health = lambda: seen.append(client.timeout) or {}
    ctx.check("the health probe uses a short timeout", client.reachable() is False and seen == [3.0])
    ctx.check("and the request timeout comes back", client.timeout == 30.0)
    ctx.check("from_config takes a timeout", Paperclip.from_config(timeout=8.0).timeout == 8.0)

    async def body():
        real = mode_mod.sync_agents
        calls = []

        def slow_sync(enabled, **kw):
            calls.append((enabled, kw.get("timeout")))
            time.sleep(1.0)
            return {"enabled": enabled, "agents": [], "note": "Paperclip is not running"}
        mode_mod.sync_agents = slow_sync
        set_config_value("paperclip.enabled", False)
        try:
            app = InitWizardApp(WizardState(cwd=REPO_DIR, step_keys=("orgs",), no_live=True))
            async with app.run_test(size=(110, 44)) as pilot:
                await pilot.pause(0.2)
                app.screen.query_one("#wiz-org-mode-switch", Switch).value = True
                t0 = time.perf_counter()
                app.screen.commit()
                spent = time.perf_counter() - t0
                ctx.check(f"commit returns at once, took {spent:.2f}s", spent < 0.5)
                ctx.check("the switch is written before commit returns", get_config_value("paperclip.enabled") is True)
                await pilot.pause(1.5)
                ctx.check(f"the courtesy ran off-thread with a short timeout, got {calls}", calls == [(True, 8.0)])
                messages = [n.message for n in app._notifications]
                ctx.check(f"its note is shown, got {messages}", any("not running" in m for m in messages))
        finally:
            mode_mod.sync_agents = real
            set_config_value("paperclip.enabled", False)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
