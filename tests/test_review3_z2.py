"""tests.test_review3_z2 -- pins for fix pass round Z, the TUI items:

  * Z4  a dialog's thread worker that raises leaves the TUI running and
        shows the error (every `tui/dialogs` worker goes through
        `worker_guard.guarded_worker`)
  * Z7  the role picker shows `assign_role`'s refusal and stays open

Run: python -m tests.test_review3_z2
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import re
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController(turns=[])
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


@test
def test_z4_a_raising_dialog_worker_reports_and_the_app_keeps_running(ctx: Ctx):
    from halo_harness.tui.dialogs.mcp_status import McpStatus

    def explode(_lines):
        raise RuntimeError("bulk result exploded")

    async def body():
        fake, app = _app()
        async with app.run_test(size=(110, 36)) as pilot:
            await pilot.pause(0.2)
            screen = McpStatus([], reconnect_all=lambda abort=None: ["all reconnected"])
            app.push_screen(screen)
            await pilot.pause(0.2)
            screen._apply_bulk_result = explode  # raises on the UI thread, re-raised in the worker
            screen.action_reconnect_all()
            await pilot.pause(0.6)
            ctx.check("the app is still running", app.is_running and app.return_code is None)
            messages = [n.message for n in app._notifications]
            ctx.check(f"the error is a notification, got {messages}",
                      any("bulk result exploded" in m and "mcp-reconnect-all" in m for m in messages))
    asyncio.run(body())


@test
def test_z4_guarded_worker_on_a_screen_and_a_plain_choice(ctx: Ctx):
    from textual.screen import ModalScreen
    from textual.widgets import Static
    from halo_harness.tui.worker_guard import guarded_worker

    class _Probe(ModalScreen):
        def compose(self):
            yield Static("probe")

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            probe = _Probe()
            app.push_screen(probe)
            await pilot.pause(0.1)

            def boom():
                raise ValueError("screen worker boom")
            w = guarded_worker(probe, boom, name="probe-boom")
            await pilot.pause(0.4)
            ctx.check("the worker belongs to the screen", w.node is probe)
            ctx.check("the app is still running", app.is_running and app.return_code is None)
            ctx.check("the error was reported", any("screen worker boom" in n.message for n in app._notifications))
            w2 = guarded_worker(probe, lambda: 7, name="probe-ok", exit_on_error=True)
            await pilot.pause(0.2)
            ctx.check("an explicit exit_on_error is passed through untouched", w2.result == 7)
    asyncio.run(body())


@test
def test_z4_no_dialog_worker_bypasses_the_guard(ctx: Ctx):
    offenders = []
    for f in sorted((REPO_DIR / "halo_harness" / "tui" / "dialogs").glob("*.py")):
        src = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\bself(?:\.app)?\.run_worker\(", src):
            call = src[m.start():m.start() + 400]
            depth, end = 0, 0
            for i, ch in enumerate(call[call.index("("):]):
                depth += ch == "("
                depth -= ch == ")"
                if depth == 0:
                    end = i
                    break
            if "exit_on_error" not in call[:call.index("(") + end + 1]:
                offenders.append(f"{f.name}:{src[:m.start()].count(chr(10)) + 1}")
    ctx.check(f"every dialog worker is guarded or chooses for itself, offenders: {offenders}", not offenders)


@test
def test_z7_role_picker_shows_the_refusal_and_stays_open(ctx: Ctx):
    import halo_harness.roles as roles
    from textual.widgets import OptionList
    from halo_harness.tui.dialogs.model_picker import RoleAssignPicker

    calls = []

    def refuse(role_name, model_ref):
        calls.append((role_name, model_ref))
        return False, ["'zz:nowhere' is not a usable model reference here: unknown provider 'zz'"]

    async def body():
        fake, app = _app()
        real = roles.assign_role
        roles.assign_role = refuse
        dismissed = []
        try:
            async with app.run_test(size=(110, 36)) as pilot:
                await pilot.pause(0.2)
                picker = RoleAssignPicker("zz:nowhere")
                app.push_screen(picker, dismissed.append)
                await pilot.pause(0.3)
                picker.query_one("#role-assign-list", OptionList).focus()
                await pilot.press("enter")
                await pilot.pause(0.3)
                ctx.check("assign_role was asked", len(calls) == 1 and calls[0][1] == "zz:nowhere")
                ctx.check("the picker is still open", app.screen is picker and dismissed == [])
                messages = [n.message for n in app._notifications]
                ctx.check(f"the reason is a notification, got {messages}",
                          any("unknown provider 'zz'" in m for m in messages))
                roles.assign_role = lambda r, m: (True, [])
                await pilot.press("enter")
                await pilot.pause(0.3)
                ctx.check(f"a choice that is accepted closes it, got {dismissed}",
                          len(dismissed) == 1 and dismissed[0] and app.screen is not picker)
        finally:
            roles.assign_role = real
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
