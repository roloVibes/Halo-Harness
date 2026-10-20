"""tests.test_tui_copy_draft -- Halo 3.1.6.0 R5 (the owner on Kali, 2026-10-20:
"Copying the words in a session chat text not yet sent does not work. I
can't copy the text then paste it somewhere else.").

The contract, through a real BridgeApp pilot on a faked Linux clipboard
environment (tests/helpers/fake_clip_env.py: `sys.platform` reads linux for
the clipboard module, PATH holds only fake tools, display/SSH/tmux vars
scrubbed):
  * Ctrl+Shift+C copies the whole chat-box draft through the clipboard tool
    on PATH, and the status line says "copied N characters via xclip";
  * `/copy draft`, typed over the draft, copies the draft it replaced
    (pastes expanded); a SENT message is no longer a draft;
  * with no tool on PATH the line names the apt install and the terminal
    that may ignore OSC 52, and the text lands in <state>/clipboard.txt;
  * the first mouse drag in the transcript or the chat box shows the
    Shift-drag hint once, never twice; a plain click shows nothing.
"""
from __future__ import annotations

TIER = "full"  # a TUI pilot (Textual run_test): the full tier

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.fake_clip_env import LinuxClipEnv
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent

test, TESTS = new_registry()


def _run(coro):
    return asyncio.run(coro)


def _app(turns=None):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController(turns=turns)
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


def _capture(app) -> list:
    notes: list = []
    app.notify = lambda msg, **kw: notes.append((str(msg), kw.get("severity")))
    return notes


async def _type_draft(app, pilot, text: str) -> None:
    app.prompt_input.text = text
    await pilot.pause(0.05)


async def _submit(app, pilot, text: str) -> None:
    from halo_harness.tui.widgets.input import PromptInput
    app.prompt_input.text = text
    await pilot.pause(0.05)
    app.prompt_input.post_message(PromptInput.Submitted(text, dict(app.prompt_input.pasted)))
    await pilot.pause(0.2)
    await app.workers.wait_for_complete()


@test
def test_ctrl_shift_c_copies_the_whole_draft_through_the_tool(ctx: Ctx):
    draft = "first line of my draft\nsecond line, not sent yet"

    async def body():
        with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0"}) as clip:
            _fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await _type_draft(app, pilot, draft)
                notes = _capture(app)
                await pilot.press("ctrl+shift+c")
                await app.workers.wait_for_complete()
                ctx.check(f"the fake xclip received the whole draft, got {clip.sink('xclip')!r}",
                          clip.sink("xclip") == draft)
                want = f"copied {len(draft)} characters via xclip"
                ctx.check(f"the status line names the count and the tool, got {notes}",
                          any(m == want and s == "information" for m, s in notes))
                ctx.check("the draft stays in the box (copying never clears it)", app.prompt_input.text == draft)
                ctx.check("no fallback file when the tool landed", not (clip.state_dir / "clipboard.txt").exists())
    _run(body())


@test
def test_ctrl_c_keeps_its_meaning_beside_the_draft_key(ctx: Ctx):
    from textual.widgets.text_area import Selection

    async def body():
        with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0"}) as clip:
            _fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await app.transcript.append_text(1, 0, "the last reply")
                await _type_draft(app, pilot, "copy only this part")
                app.prompt_input.selection = Selection((0, 10), (0, 19))
                notes = _capture(app)
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"a chat-box selection + Ctrl+C copies just the selection, got {clip.sink('xclip')!r}",
                          clip.sink("xclip") == "this part")
                ctx.check(f"with its status line, got {notes}", any(m == "copied 9 characters via xclip" for m, _s in notes))
                app.prompt_input.selection = Selection((0, 0), (0, 0))
                await pilot.press("ctrl+c")
                await app.workers.wait_for_complete()
                ctx.check(f"no selection: Ctrl+C still copies the last reply, got {clip.sink('xclip')!r}",
                          clip.sink("xclip") == "the last reply")
                ctx.check("and arms the double-press quit window", app._ctrl_c_deadline is not None)
    _run(body())


@test
def test_copy_draft_command_copies_the_draft_it_was_typed_over(ctx: Ctx):
    pasted = "\n".join(f"pasted row {i}" for i in range(6))

    async def body():
        with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0"}) as clip:
            _fake, app = _app(turns=[])
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await _type_draft(app, pilot, "see this: ")
                app.prompt_input.move_cursor(app.prompt_input.document.end)
                app.prompt_input.paste_text(pasted)
                await pilot.pause(0.1)
                ctx.check(f"the paste became a placeholder, got {app.prompt_input.text!r}",
                          "[Pasted text #1" in app.prompt_input.text)
                notes = _capture(app)
                await _submit(app, pilot, "/copy draft")
                want_text = "see this: " + pasted
                ctx.check(f"/copy draft copied the replaced draft with the paste expanded, got "
                          f"{clip.sink('xclip')!r}", clip.sink("xclip") == want_text)
                ctx.check(f"the status line names the count and xclip, got {notes}",
                          any(m == f"copied {len(want_text)} characters via xclip" for m, _s in notes))
                ctx.check(f"the immediate line names the draft, got {notes}",
                          any(m.startswith("Copied the draft (") for m, _s in notes))
    _run(body())


@test
def test_a_sent_message_is_no_longer_a_draft(ctx: Ctx):
    async def body():
        with LinuxClipEnv(tools=("xclip",), env={"DISPLAY": ":0"}) as clip:
            fake, app = _app(turns=[])
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await _submit(app, pilot, "this one is sent")
                ctx.check(f"the message reached the controller, got {fake.submitted}",
                          "this one is sent" in fake.submitted)
                notes = _capture(app)
                await _submit(app, pilot, "/copy draft")
                ctx.check(f"nothing copied, got {clip.sink('xclip')!r}", clip.sink("xclip") == "")
                ctx.check(f"the line says there is nothing to copy, got {notes}",
                          any("Nothing in the chat box to copy" in m and s == "warning" for m, s in notes))
    _run(body())


@test
def test_no_tool_on_path_saves_the_file_and_names_the_apt_install(ctx: Ctx):
    draft = "words that must not be lost"

    async def body():
        with LinuxClipEnv(env={"DISPLAY": ":0", "TERMINAL": "/usr/bin/qterminal",
                               "COLORTERM": "truecolor"}) as clip:
            _fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await _type_draft(app, pilot, draft)
                notes = _capture(app)
                await pilot.press("ctrl+shift+c")
                await app.workers.wait_for_complete()
                saved = clip.state_dir / "clipboard.txt"
                ctx.check("the text was written to <state>/clipboard.txt",
                          saved.exists() and saved.read_text(encoding="utf-8") == draft)
                if sys.platform != "win32":
                    ctx.check(f"the file is 0600, got {oct(saved.stat().st_mode & 0o777)}",
                              saved.stat().st_mode & 0o777 == 0o600)
                line = next((m for m, s in notes if m.startswith("no clipboard tool")), "")
                ctx.check(f"the line names the apt install, got {notes}",
                          line.startswith("no clipboard tool: sudo apt install xclip (or wl-clipboard on Wayland); "
                                          "sent OSC 52, which qterminal may ignore"))
                ctx.check(f"the line names the file and the count, got {line!r}",
                          "clipboard.txt" in line and f"saved {len(draft)} characters" in line)
    _run(body())


@test
def test_shift_drag_hint_shows_once_and_a_click_shows_nothing(ctx: Ctx):
    from textual import events
    from halo_harness.tui.draft_copy import SHIFT_HINT

    async def body():
        with LinuxClipEnv(env={"DISPLAY": ":0"}):
            _fake, app = _app()
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                notes = _capture(app)
                await pilot._post_mouse_events([events.MouseDown, events.MouseUp], app.prompt_input,
                                               offset=(2, 0), button=1)
                await pilot.pause(0.05)
                ctx.check(f"a plain click shows no hint, got {notes}", not any(m == SHIFT_HINT for m, _s in notes))
                await pilot._post_mouse_events([events.MouseDown, events.MouseMove, events.MouseUp],
                                               app.transcript, offset=(3, 2), button=1)
                await pilot.pause(0.05)
                ctx.check(f"a drag in the transcript shows the hint, got {notes}",
                          sum(1 for m, _s in notes if m == SHIFT_HINT) == 1)
                await pilot._post_mouse_events([events.MouseDown, events.MouseMove, events.MouseUp],
                                               app.prompt_input, offset=(2, 0), button=1)
                await pilot.pause(0.05)
                ctx.check(f"a second drag (the chat box) does not repeat it, got {notes}",
                          sum(1 for m, _s in notes if m == SHIFT_HINT) == 1)
                ctx.check("the hint is pinned as shown for the session", app._shift_drag_hint.shown is True)
    _run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
