"""tests.test_ctrl_c_copy_quit -- Halo 2.0.7 round 7c (rolo 2026-10-09: "When I
press Ctrl+C once in a Halo session in PowerShell, it closes. I need Ctrl+C
for copying. The first Ctrl+C should copy; if a user does that twice they
probably want to quit, and a popup should show confirming").

The contract:
  * the first Ctrl+C copies a selection, else the last assistant reply, and
    says "Copied N characters" / "Nothing to copy"; it never interrupts a
    running turn (Esc does);
  * a second press within DOUBLE_CTRL_C_WINDOW_S (3 s) opens the "Quit
    Halo?" card -- Enter quits, Esc stays and the window resets;
  * quit_on_double_ctrl_c: false means every press just copies;
  * the Windows console helper clears ENABLE_PROCESSED_INPUT, swallows
    CTRL_C_EVENT, restores everything, and is inert on POSIX.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent

test, TESTS = new_registry()


class _Env:
    """Scoped state dir + a clipboard sink in place of the OS clipboard."""

    def __init__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = tempfile.mkdtemp(prefix="ctrlc-")
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ["BRIDGE_STATE_DIR"] = d
        import halo_harness.tui.clipboard as clipboard_mod
        self.sink: list = []
        self._clip = clipboard_mod
        self._real = clipboard_mod.copy_via_external_tool
        clipboard_mod.copy_via_external_tool = lambda text, **kw: (self.sink.append(text) or True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._clip.copy_via_external_tool = self._real
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _run(coro):
    return asyncio.run(coro)


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController()
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


def _capture_notices(app) -> list:
    notices: list = []
    app.notify = lambda msg, **kw: notices.append(msg)
    return notices


def _card_open(app) -> bool:
    from halo_harness.tui.dialogs.quit_confirm import QuitConfirmScreen
    return isinstance(app.screen, QuitConfirmScreen)


@test
def test_window_is_three_seconds_and_card_wording(ctx: Ctx):
    from halo_harness.tui.dialogs.quit_confirm import QUIT_CARD_HINT, QUIT_CARD_TITLE
    from halo_harness.tui.keys import DOUBLE_CTRL_C_WINDOW_S
    ctx.check("window is 3 s", DOUBLE_CTRL_C_WINDOW_S == 3.0)
    ctx.check("card title", QUIT_CARD_TITLE == "Quit Halo?")
    ctx.check("card hint", QUIT_CARD_HINT == "Enter quits, Esc stays")


@test
def test_ctrl_c_with_a_transcript_selection_copies_it(ctx: Ctx):
    from textual.selection import Offset, Selection

    async def body():
        with _Env() as env:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                from halo_harness.tui.widgets.transcript import SystemNote
                note = SystemNote("line zero\nline one\nline two\nline three", kind="note")
                await app.transcript.mount(note)
                await pilot.pause(0.1)
                app.screen.selections = {note: Selection(Offset(0, 1), Offset(8, 2))}
                notices = _capture_notices(app)
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"range copied to the sink, got {env.sink}", env.sink == ["line one\nline two"])
                ctx.check(f"toast shown, got {notices}", any("Copied selection (17 characters)" in m for m in notices))
                ctx.check("a selection copy does not arm the window", app._ctrl_c_deadline is None)
    _run(body())


@test
def test_ctrl_c_without_selection_copies_the_last_reply(ctx: Ctx):
    async def body():
        with _Env() as env:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await app.transcript.append_text(1, 0, "the last reply text")
                notices = _capture_notices(app)
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"last reply reached the sink, got {env.sink}", env.sink == ["the last reply text"])
                ctx.check(f"toast 'Copied N characters', got {notices}",
                          any(m.startswith("Copied 19 characters") for m in notices))
                ctx.check("the first press did not quit", fake.quit_called is False and not _card_open(app))
    _run(body())


@test
def test_ctrl_c_on_an_empty_transcript_says_nothing_to_copy(ctx: Ctx):
    async def body():
        with _Env() as env:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                notices = _capture_notices(app)
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"toast says Nothing to copy, got {notices}", any(m.startswith("Nothing to copy") for m in notices))
                ctx.check("nothing reached the clipboard sink", env.sink == [])
    _run(body())


@test
def test_ctrl_c_never_interrupts_a_running_turn(ctx: Ctx):
    async def body():
        with _Env():
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                app._turn_running = True
                notices = _capture_notices(app)
                before = fake.interrupts
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"no interrupt was sent, got {fake.interrupts - before}", fake.interrupts == before)
                ctx.check(f"the toast points at Esc, got {notices}", any("Esc interrupts the running turn" in m for m in notices))
                app._turn_running = False
    _run(body())


@test
def test_two_presses_open_the_card_and_enter_quits(ctx: Ctx):
    async def body():
        with _Env():
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await pilot.press("ctrl+c")
                ctx.check("first press: no card", not _card_open(app))
                await pilot.press("ctrl+c")
                await pilot.pause(0.1)
                ctx.check("second press within the window opens the card", _card_open(app))
                ctx.check("the card never quits by itself", fake.quit_called is False)
                await pilot.press("ctrl+c")
                ctx.check("a third press with the card open changes nothing", _card_open(app) and fake.quit_called is False)
                await pilot.press("enter")
                await pilot.pause(0.3)
            ctx.check("Enter ran the existing quit path", fake.quit_called is True)
            ctx.check(f"clean exit code, got {app.return_code}", app.return_code == 0)
    _run(body())


@test
def test_esc_stays_and_a_later_press_copies_again(ctx: Ctx):
    async def body():
        with _Env() as env:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await app.transcript.append_text(1, 0, "reply")
                await pilot.press("ctrl+c")
                await pilot.press("ctrl+c")
                await pilot.pause(0.1)
                ctx.check("card open", _card_open(app))
                await pilot.press("escape")
                await pilot.pause(0.1)
                ctx.check("Esc closed the card", not _card_open(app))
                ctx.check("Esc did not quit", fake.quit_called is False)
                ctx.check("the window was reset", app._ctrl_c_deadline is None)
                env.sink.clear()
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check("the next press copied again instead of opening the card",
                          not _card_open(app) and env.sink == ["reply"])
    _run(body())


@test
def test_a_press_outside_the_window_copies(ctx: Ctx):
    async def body():
        with _Env() as env:
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await app.transcript.append_text(1, 0, "reply")
                await pilot.press("ctrl+c")
                app._ctrl_c_deadline = time.monotonic() - 0.5  # the window has lapsed
                env.sink.clear()
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check("no card after the window lapsed", not _card_open(app))
                ctx.check(f"it copied again, got {env.sink}", env.sink == ["reply"])
    _run(body())


@test
def test_switch_off_disables_the_card(ctx: Ctx):
    from halo_harness import theme as theme_mod

    async def body():
        with _Env() as env:
            theme_mod.set_config_value("quit_on_double_ctrl_c", False)
            fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await app.transcript.append_text(1, 0, "reply")
                await pilot.press("ctrl+c")
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check("no card with the switch off", not _card_open(app))
                ctx.check(f"each press copied, got {env.sink}", env.sink == ["reply", "reply"])
                ctx.check("never armed", app._ctrl_c_deadline is None)
    _run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
