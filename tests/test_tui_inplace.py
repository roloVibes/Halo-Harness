"""tests.test_tui_inplace -- Halo 3.1.3.0 R2: the terminal keeps up with
the typist. The status bar and the thinking block used to
ask Textual for a full screen layout on every periodic repaint (every
transcript widget, thousands in a long session), and keys typed meanwhile
waited behind it. Pinned here:

- periodic repaints (status-bar ticks) make no layout request
  of their own once the widgets are laid out (`tui/widgets/inplace.py`);
- the slash completion popup rebuilds once per change, not once per entry,
  and a repeat of the same list is a no-op;
- typing into a filled transcript costs far fewer screen layouts than keys
  and loses no characters;
- a terminal resize draws no layout request from the status bar beyond
  Textual's own (it used to add one).

Run: python -m tests.test_tui_inplace
"""

from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import contextlib
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.layout_watch import watch_own_layout_requests  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()

MD = ("## Heading\n\nSome **bold** text and `code`, a list:\n\n- one\n- two\n\n"
      "```python\ndef f(x):\n    return x * 2\n```\n")


def _app(theme: str = "claude-dark"):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project", theme_name=theme)


@contextlib.contextmanager
def _count_layouts():
    """Count Textual's screen layouts while the block runs."""
    from textual.screen import Screen
    counted = []
    orig = Screen._refresh_layout

    def counting(self, *a, **k):
        counted.append(1)
        return orig(self, *a, **k)

    Screen._refresh_layout = counting
    try:
        yield counted
    finally:
        Screen._refresh_layout = orig


async def _fill(app, pilot, turns: int) -> None:
    for i in range(turns):
        await app.transcript.add_note(f"note {i}: " + "words " * 20)
        await app.transcript.append_text(i, 0, MD)
    await _settle(pilot)


async def _settle(pilot) -> None:
    """Wait until a quarter second passes with no screen layout (a slow
    runner takes longer to digest the transcript)."""
    for _ in range(40):
        with _count_layouts() as counted:
            await pilot.pause(0.25)
        if not counted:
            return


@test
def test_periodic_repaints_ask_for_no_screen_layout(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            await _fill(app, pilot, 6)
            bar = app.status_bar
            bar.set_phase_word("thinking")
            # a status line wider than the terminal: the row stays one row
            # (`height: 1`), so measuring its wrapped content must not count
            bar.set_statusline_text("statusline " * 40)
            await _settle(pilot)
            with watch_own_layout_requests(bar) as asked:
                for _ in range(5):
                    bar.tick_spinner()
                    bar._refresh_display()
                await pilot.pause(0.1)
            facts = f"bar height={bar.styles.height} content={bar.content_size}"
            ctx.check(f"five status-bar ticks make no layout request, got {asked} ({facts})", not asked)
    asyncio.run(body())


@test
def test_the_completion_popup_rebuilds_once_per_change(ctx: Ctx):
    from halo_harness.tui.widgets.input import CompletionPopup

    async def body():
        app = _app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            popup = app.query_one(CompletionPopup)
            clears = []
            orig = popup.clear_options

            def clearing():
                clears.append(1)
                return orig()

            popup.clear_options = clearing
            popup.show(["/model", "/mode"])
            await pilot.pause(0.05)
            ctx.check(f"a list shows its entries, got {popup.option_count}", popup.option_count == 2 and popup.display)
            popup.show(["/model", "/mode"])
            ctx.check(f"the same list again rebuilds nothing, got {len(clears)} rebuilds", len(clears) == 1)
            popup.show(["/model"])
            ctx.check(f"a changed list rebuilds once, got {popup.option_count} entries after {len(clears)} rebuilds",
                      popup.option_count == 1 and len(clears) == 2)
            popup.hide()
            popup.hide()
            ctx.check(f"hiding twice clears once, got {len(clears)} rebuilds, display {popup.display}",
                      len(clears) == 3 and not popup.display)
    asyncio.run(body())


@test
def test_typing_into_a_filled_transcript_is_cheap_and_loses_nothing(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            await _fill(app, pilot, 12)
            app.prompt_input.focus()
            await _settle(pilot)
            text = "the quick brown fox"
            with _count_layouts() as counted:
                for ch in text:
                    await pilot.press("space" if ch == " " else ch)
                await pilot.pause(0.1)
            ctx.check(f"typed text arrives whole, got {app.prompt_input.text!r}", app.prompt_input.text == text)
            ctx.check(f"a line of typing costs far fewer screen layouts than keys (was one per key), got {len(counted)}",
                      len(counted) < len(text) // 2)
            app.prompt_input.text = ""
            await _settle(pilot)
            with _count_layouts() as counted:
                for key in ("slash", "m", "o", "d"):
                    await pilot.press(key)
                await pilot.pause(0.1)
            ctx.check(f"a slash command arrives whole, got {app.prompt_input.text!r}", app.prompt_input.text == "/mod")
            ctx.check(f"opening the slash menu costs at most a few screen layouts, got {len(counted)}", len(counted) <= 4)
    asyncio.run(body())


@test
def test_a_resize_draws_no_layout_request_from_the_status_bar(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)
            await _fill(app, pilot, 8)
            bar = app.status_bar
            with watch_own_layout_requests(bar) as asked:
                await pilot.resize_terminal(119, 40)
                await pilot.pause(0.3)
            ctx.check(f"the status bar repaints in place after a resize, got {asked}", not asked)
            ctx.check(f"and stays one row, got {bar.size.height}", bar.size.height == 1)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
