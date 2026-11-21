"""tests.test_tui_copy_selection -- Halo 3.6.0.6 package C (the owner, 2026-11-20: "Copying from the session barely
works!"). A real mouse drag through Textual's pilot (press, move, release) over the transcript, then what reached the
clipboard function. The older copy tests set a selection on a SystemNote by hand and never dragged inside a reply,
which is why they passed while every drag over an answer copied the LAST answer.

The contract:
  * the words dragged over are the words copied: inside a reply (its Markdown blocks have no `copy_text`, so
    Textual's own text for the dragged range is used), from a paragraph into a code block (indentation and line
    breaks kept), one word of a one-line row (judged by rows AND columns); a drag over a whole widget copies its
    SOURCE; Ctrl+C with nothing selected copies the last reply and says so;
  * a drag copies at once when the mouse is let go ("Copied the selection (N characters)"), once per selection; a
    plain click copies nothing; Ctrl+C copies the same selection again and never arms the quit window;
  * a click on a transcript card leaves the keyboard in the chat box; Tab and the card's own keys still work.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent

test, TESTS = new_registry()

REPLY_ONE = ("First answer ALPHA-ONE with some words.\n\n"
             "```python\ndef hello():\n    # KEEP-INDENT\n    return 1\n```")
REPLY_TWO = "SECOND-REPLY only, the last one."


class _Env:
    """A scoped state dir and a clipboard sink in place of the system's clipboard program."""

    def __init__(self, lands: bool = True):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        self.dir = tempfile.mkdtemp(prefix="copysel-")
        os.environ["BRIDGE_TEST_HOME"] = self.dir
        os.environ["BRIDGE_STATE_DIR"] = self.dir
        import halo_harness.tui.clipboard as clipboard_mod
        self.sink: list = []
        self._clip = clipboard_mod
        self._real = clipboard_mod.copy_via_external_tool
        self._real_trusted = clipboard_mod.osc52_trusted
        clipboard_mod.copy_via_external_tool = lambda text, **kw: (self.sink.append(text) or lands)
        clipboard_mod.osc52_trusted = lambda *a, **kw: False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._clip.copy_via_external_tool = self._real
        self._clip.osc52_trusted = self._real_trusted
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


def _capture(app) -> list:
    notices: list = []
    app.notify = lambda msg, **kw: notices.append(msg)
    return notices


def _full_text(widget) -> str:
    from textual.selection import SELECT_ALL
    got = widget.get_selection(SELECT_ALL)
    return got[0] if got else ""


def _leaf_with(root, word: str):
    """The innermost widget under `root` (or `root` itself) whose drawn text holds `word`."""
    found = None
    for w in [root, *root.walk_children()]:
        if w.region.height and word in _full_text(w):
            found = w
    return found


def _cell(widget, word: str, *, end: bool = False) -> "tuple[int, int]":
    """The screen cell of the first (or, with end=True, the last) character of `word` in `widget`'s drawn text."""
    text = _full_text(widget)
    at = text.index(word) + (len(word) - 1 if end else 0)
    line = text.count("\n", 0, at)
    col = at - (text.rfind("\n", 0, at) + 1)
    region = widget.content_region
    return region.x + col, region.y + line


async def _drag(pilot, start, end) -> None:
    await pilot.mouse_down(offset=start)
    await pilot.hover(offset=((start[0] + end[0]) // 2, start[1]))
    await pilot.hover(offset=end)
    await pilot.mouse_up(offset=end)
    await pilot.pause(0.1)


async def _two_replies(app, pilot):
    """Ask, answer, ask, answer -- the second answer is the LAST one. Returns the two AssistantText widgets."""
    from halo_harness.tui.widgets.transcript import AssistantText
    await pilot.pause(0.2)
    await app.transcript.add_user("ASK-ONE please")
    await app.transcript.append_text(1, 0, REPLY_ONE)
    await app.transcript.add_user("ASK-TWO")
    await app.transcript.append_text(2, 0, REPLY_TWO)
    replies = []
    for _ in range(60):
        await pilot.pause(0.05)
        replies = [w for w in app.transcript.widgets_in_order() if isinstance(w, AssistantText)]
        if len(replies) == 2 and _leaf_with(replies[0], "KEEP-INDENT") and _leaf_with(replies[1], "SECOND-REPLY"):
            break
    return replies


# ---- entry 1: the dragged words are the copied words ------------------------------------------------------------


@test
def test_a_drag_over_words_of_an_earlier_reply_copies_those_words(ctx: Ctx):
    async def body():
        with _Env() as env:
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                first, _last = await _two_replies(app, pilot)
                para = _leaf_with(first, "ALPHA-ONE")
                await _drag(pilot, _cell(para, "ALPHA-ONE"), _cell(para, "with some", end=True))
                env.sink.clear()
                notices = _capture(app)
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"Ctrl+C copied the dragged words, got {env.sink}", env.sink == ["ALPHA-ONE with some"])
                ctx.check(f"not the last reply, got {env.sink}", not any("SECOND-REPLY" in s for s in env.sink))
                ctx.check(f"the toast names the selection, got {notices}",
                          "Copied the selection (19 characters)" in notices)
                ctx.check("a selection copy does not arm the quit window", app._ctrl_c_deadline is None)
    _run(body())


@test
def test_a_drag_from_a_paragraph_into_the_code_keeps_indentation(ctx: Ctx):
    async def body():
        with _Env() as env:
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                first, _last = await _two_replies(app, pilot)
                para = _leaf_with(first, "ALPHA-ONE")
                code = _leaf_with(first, "KEEP-INDENT")
                # Across widgets Textual's end cell is exclusive (its highlight shows the same range): let go one
                # cell past the word, as a person does.
                end_x, end_y = _cell(code, "KEEP-INDENT", end=True)
                await _drag(pilot, _cell(para, "ALPHA-ONE"), (end_x + 1, end_y))
                got = app._selected_transcript_text() or ""
                ctx.check(f"starts at the dragged word, got {got!r}", got.startswith("ALPHA-ONE with some words."))
                ctx.check(f"the code keeps its line break and indentation, got {got!r}",
                          "def hello():\n    # KEEP-INDENT" in got)
                ctx.check(f"nothing past the drag, got {got!r}", "return 1" not in got and "SECOND" not in got)
    _run(body())


@test
def test_a_drag_over_one_word_of_a_one_line_row_copies_that_word(ctx: Ctx):
    async def body():
        with _Env():
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                await _two_replies(app, pilot)
                from halo_harness.tui.widgets.transcript import UserMessage
                row = [w for w in app.transcript.widgets_in_order() if isinstance(w, UserMessage)][0]
                await _drag(pilot, _cell(row, "please"), _cell(row, "please", end=True))
                got = app._selected_transcript_text()
                ctx.check(f"just the word, got {got!r}", got == "please")
    _run(body())


@test
def test_a_drag_over_a_whole_reply_copies_its_source(ctx: Ctx):
    from textual.selection import SELECT_ALL

    async def body():
        with _Env():
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                first, _last = await _two_replies(app, pilot)
                para = _leaf_with(first, "ALPHA-ONE")
                code = _leaf_with(first, "KEEP-INDENT")
                start = _cell(para, "First")
                last_line = _full_text(code).splitlines()[-1]
                end = _cell(code, last_line, end=True)
                await _drag(pilot, start, (end[0] + 3, end[1]))
                got = app._selected_transcript_text()
                ctx.check(f"the reply's markdown source, got {got!r}", got == REPLY_ONE)
                # A whole one-line row: its source, without the drawn prompt arrow.
                from halo_harness.tui.widgets.transcript import UserMessage
                row = [w for w in app.transcript.widgets_in_order() if isinstance(w, UserMessage)][1]
                app.screen.selections = {row: SELECT_ALL}
                ctx.check(f"a whole row is its source, got {app._selected_transcript_text()!r}",
                          app._selected_transcript_text() == "ASK-TWO")
    _run(body())


@test
def test_ctrl_c_with_nothing_selected_says_it_copied_the_last_reply(ctx: Ctx):
    async def body():
        with _Env() as env:
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                await _two_replies(app, pilot)
                notices = _capture(app)
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"the last reply, got {env.sink}", env.sink == [REPLY_TWO])
                ctx.check(f"the toast says so, got {notices}",
                          f"Copied the last reply ({len(REPLY_TWO)} characters)" in notices)
                ctx.check("this press arms the quit window", app._ctrl_c_deadline is not None)
    _run(body())


# ---- entry 2: a drag copies when the mouse is let go -------------------------------------------------------------


@test
def test_letting_go_of_a_drag_copies_the_words_at_once(ctx: Ctx):
    async def body():
        with _Env() as env:
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                first, _last = await _two_replies(app, pilot)
                para = _leaf_with(first, "ALPHA-ONE")
                notices = _capture(app)
                await _drag(pilot, _cell(para, "ALPHA-ONE"), _cell(para, "with some", end=True))
                await app.workers.wait_for_complete()
                ctx.check(f"no key pressed, the words reached the clipboard, got {env.sink}",
                          env.sink == ["ALPHA-ONE with some"])
                ctx.check(f"the toast says so, got {notices}", "Copied the selection (19 characters)" in notices)
                ctx.check("the selection stays drawn", bool(app.screen.selections))
                # The same selection reported again (a second mouse-up that changed nothing) is not copied again.
                from textual import events
                app.screen.post_message(events.TextSelected())
                await pilot.pause(0.1)
                await app.workers.wait_for_complete()
                ctx.check(f"copied once, got {env.sink}", env.sink == ["ALPHA-ONE with some"])
                # Ctrl+C copies the same words again and never arms the quit window.
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"Ctrl+C copies it again, got {env.sink}",
                          env.sink == ["ALPHA-ONE with some", "ALPHA-ONE with some"])
                ctx.check("no quit window", app._ctrl_c_deadline is None)
                # A new drag over the very same words copies again (the clipboard may hold something else by now:
                # seen in a real qterminal, where the second drag left the old clipboard).
                await _drag(pilot, _cell(para, "ALPHA-ONE"), _cell(para, "with some", end=True))
                await app.workers.wait_for_complete()
                ctx.check(f"the same drag again copies again, got {env.sink}", env.sink == ["ALPHA-ONE with some"] * 3)
    _run(body())


@test
def test_a_plain_click_copies_nothing_and_says_nothing(ctx: Ctx):
    async def body():
        with _Env() as env:
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                first, _last = await _two_replies(app, pilot)
                para = _leaf_with(first, "ALPHA-ONE")
                notices = _capture(app)
                at = _cell(para, "ALPHA-ONE")
                await pilot.mouse_down(offset=at)
                await pilot.mouse_up(offset=at)
                await pilot.pause(0.1)
                await app.workers.wait_for_complete()
                ctx.check(f"nothing copied, got {env.sink}", env.sink == [])
                ctx.check(f"nothing said about a copy, got {notices}", not any("opied" in m for m in notices))
    _run(body())


@test
def test_a_drag_with_no_clipboard_program_says_the_fix_once(ctx: Ctx):
    async def body():
        with _Env(lands=False) as env:
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                first, _last = await _two_replies(app, pilot)
                para = _leaf_with(first, "ALPHA-ONE")
                notices: list = []
                app.notify = lambda msg, **kw: notices.append((msg, kw.get("severity")))
                await _drag(pilot, _cell(para, "ALPHA-ONE"), _cell(para, "with some", end=True))
                await app.workers.wait_for_complete()
                from textual import events
                app.screen.post_message(events.TextSelected())
                await pilot.pause(0.1)
                await app.workers.wait_for_complete()
                failures = [m for m, s in notices if s == "error" and "Copy FAILED" in m]
                ctx.check(f"one failure line naming the fix, got {notices}", len(failures) == 1)
                saved = Path(env.dir) / "clipboard.txt"
                ctx.check(f"the text was saved to {saved}",
                          saved.is_file() and saved.read_text(encoding="utf-8") == "ALPHA-ONE with some")
    _run(body())


# ---- entry 3: a click on a card leaves the keyboard in the chat box ----------------------------------------------


@test
def test_a_click_on_a_tool_card_leaves_the_keys_in_the_chat_box(ctx: Ctx):
    async def body():
        with _Env() as env:
            _fake, app = _app()
            async with app.run_test(size=(100, 50)) as pilot:
                await _two_replies(app, pilot)
                from halo_harness.tui.widgets.cards import PagerScreen, ToolCard
                card = ToolCard(tool_use_id="t-1", header="⏺ Read(notes.txt)")
                await app.transcript.mount_tool_card(card)
                card.set_result(ok=True, summary="1 line", content="NOTE-LINE-1 plain")
                await pilot.pause(0.2)
                await pilot.click(card)
                await pilot.pause(0.1)
                for key in ("slash", "c", "o", "p", "y"):
                    await pilot.press(key)
                await pilot.pause(0.1)
                ctx.check(f"the chat box holds /copy, got {app.prompt_input.text!r}", app.prompt_input.text == "/copy")
                ctx.check(f"no pager was opened, got {type(app.screen).__name__}",
                          not isinstance(app.screen, PagerScreen))
                # The keyboard path is unchanged: a card that has the focus still takes its own keys.
                env.sink.clear()
                card.focus()
                await pilot.pause(0.05)
                await pilot.press("y")
                await app.workers.wait_for_complete()
                ctx.check(f"y on a card reached by the keyboard copies it, got {env.sink}",
                          len(env.sink) == 1 and "NOTE-LINE-1" in env.sink[0])
    _run(body())


@test
def test_no_transcript_card_takes_the_focus_on_a_click(ctx: Ctx):
    from halo_harness.tui.widgets import cards, eyes_card, lane_offer, preflight_card, review_cards
    classes = [cards.ToolCard, cards.PermissionCard, cards.QuestionCard, cards.PlanCard, cards.ApprovalCard,
               cards.EffortCard, cards.RewindCard, eyes_card.EyesCard, preflight_card.PreflightCard,
               lane_offer.LaneOfferCard, review_cards.ReviewCard]
    for cls in classes:
        ctx.check(f"{cls.__name__} can still take the focus from the keyboard", cls.can_focus is True)
        ctx.check(f"{cls.__name__} does not take it on a click", cls.FOCUS_ON_CLICK is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
