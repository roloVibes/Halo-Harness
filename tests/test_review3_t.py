"""tests.test_review3_t -- pins for the 3.0.2.0 review fix pass, round T-tui
(TUI core):

  * item 11  a card arriving under a dialog never takes the dialog's keys
  * item 12  escape sequences in tool output / model text are shown, never sent
  * item 73  a thread worker that raises leaves the TUI running
  * item 74  pastes and typed SGR literals are never stripped

Dialog/theme items are in tests/test_review3_t2.py and _t3.py; 144/145 in _t4.

Run: python -m tests.test_review3_t
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from halo_harness import events as ev  # noqa: E402

test, TESTS = new_registry()

HOSTILE = "before \x1b]52;c;SGVsbG8=\x1b\\ middle \x1b[2J\x1b]0;pwned\x07 after \x9b31m end"


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    fake = FakeController(turns=[])
    return fake, BridgeApp(fake, cwd=str(REPO_DIR))


def _permission_event(rid: str = "req-1"):
    return ev.Event("permission_request", {"id": rid, "name": "Bash", "input": {"command": "rm -rf build"},
                                           "reason": "not covered by a rule", "suggested_rule": "Bash(rm:*)"}, turn=1)


@test
def test_item11_a_card_under_a_dialog_never_answers_the_dialogs_keys(ctx: Ctx):
    from halo_harness.tui.dialogs.session_picker import SessionPicker
    from halo_harness.tui.dispatch import apply_event

    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            row = {"id": "s1", "cwd": str(REPO_DIR), "mtime": 0, "summary": "hello", "title": "one",
                   "model": "", "cost_usd": 0.0, "turns": 1}
            app.push_screen(SessionPicker([row]))
            await pilot.pause(0.2)
            picker = app.screen
            await apply_event(app, _permission_event())
            await pilot.pause(0.1)
            ctx.check("the card is pending", app.pending_card is not None)
            ctx.check(f"the dialog keeps its focus, got {type(picker.focused).__name__}",
                      picker.focused is not None and picker.focused is not app.pending_card)
            for key in ("1", "3", "4"):
                await pilot.press(key)
            await pilot.pause(0.1)
            ctx.check(f"no reply went out, got {fake.permission_replies}", fake.permission_replies == [])
            ctx.check(f"no rule was written, got {fake.added_rules}", fake.added_rules == [])
            value = picker.query_one("#resume-filter").value
            ctx.check(f"the digits reached the filter box, got {value!r}", value == "134")
            ctx.check("the card's keys are switched off while it is covered",
                      app.pending_card.check_action("choose_once", ()) is False)
            await pilot.press("escape")
            await pilot.pause(0.2)
            ctx.check(f"back on the base screen the card has focus, got {type(app.focused).__name__}",
                      app.focused is app.pending_card)
            await pilot.press("1")
            await pilot.pause(0.1)
            ctx.check(f"now 1 answers it, got {fake.permission_replies}",
                      [r[1]["action"] for r in fake.permission_replies] == ["allow"])
            app.push_screen(SessionPicker([row]))
            await pilot.pause(0.2)
            focused = app.screen.focused
            app.clear_pending_card()
            ctx.check("clearing a card under a dialog leaves the dialog's focus alone", app.screen.focused is focused)
    asyncio.run(body())


@test
def test_item12_escape_sequences_are_shown_never_sent(ctx: Ctx):
    from halo_harness.tui.dispatch import apply_event
    from halo_harness.tui.widgets.input_sanitize import display_safe, display_safe_content
    from rich.text import Text

    ctx.check("display_safe keeps length", len(display_safe(HOSTILE)) == len(HOSTILE))
    ctx.check("display_safe leaves no ESC or C1", not any(c in display_safe(HOSTILE) for c in "\x1b\x9b\x07"))
    styled = Text("ok \x1b[2J", style="bold")
    styled.stylize("red", 0, 2)
    safe = display_safe_content(styled)
    ctx.check("a Rich Text keeps its spans", safe.spans == styled.spans and "\x1b" not in safe.plain)
    ctx.check("tabs and newlines survive", display_safe("a\tb\nc") == "a\tb\nc")

    async def body():
        fake, app = _app()
        async with app.run_test(size=(140, 60)) as pilot:
            await pilot.pause(0.2)
            await apply_event(app, ev.Event("tool_use_ready", {"id": "tu1", "name": "Bash",
                                                               "input": {"command": "cat README.md"}, "repaired": False}, turn=1))
            await apply_event(app, ev.Event("tool_result", {"id": "tu1", "ok": True, "summary": "README",
                                                            "content": HOSTILE}, turn=1))
            await app.transcript.add_note("note: " + HOSTILE)
            await apply_event(app, ev.message_start(turn=1))
            await apply_event(app, ev.text_delta("model says " + HOSTILE, turn=1))
            await pilot.pause(0.6)
            strips = app.screen._compositor.render_strips()
            shown = "\n".join(strip.text for strip in strips)
            ctx.check("the hostile text is on screen", "middle" in shown and "␛" in shown)
            ctx.check("no ESC, BEL or C1 inside the rendered text", not any(c in shown for c in "\x1b\x9b\x07"))
            raw = app.screen._compositor.render_full_update().render_segments(app.console)
            for seq in ("\x1b]52;", "\x1b[2J", "\x1b]0;"):
                ctx.check(f"the terminal never receives {seq!r}", seq not in raw)
            app.tui_setting = "inline"
            message = app._build_scrollback_message() or ""
            ctx.check("the after-exit scrollback is clean too", "middle" in message and "\x1b" not in message)
    asyncio.run(body())


@test
def test_item73_a_raising_worker_reports_and_the_app_keeps_running(ctx: Ctx):
    import halo_harness.doctor as doctor_mod
    from halo_harness.tui.slash import handle_slash

    def boom(**_kw):
        raise RuntimeError("probe exploded")

    async def body():
        fake, app = _app()
        real = doctor_mod.run_checks
        doctor_mod.run_checks = boom
        try:
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.2)
                await handle_slash(app, "doctor", "")
                await pilot.pause(0.5)
                ctx.check("the app is still running", app.is_running and app.return_code is None)
                messages = [n.message for n in app._notifications]
                ctx.check(f"the error is a notification, got {messages}",
                          any("probe exploded" in m for m in messages))
        finally:
            doctor_mod.run_checks = real
    asyncio.run(body())


@test
def test_item73_list_sessions_skips_a_file_that_vanished(ctx: Ctx):
    from halo_harness.controller import Controller, project_slug
    import pathlib

    root = Path(tempfile.mkdtemp(prefix="r3t-sessions-"))
    cwd = root / "proj"
    cwd.mkdir()
    sessions = root / "sessions" / project_slug(cwd)
    sessions.mkdir(parents=True)
    (sessions / "keep.jsonl").write_text('{"type": "user", "content": [{"type": "text", "text": "hi"}]}\n')
    gone = sessions / "gone.jsonl"
    gone.write_text("")
    real_stat = pathlib.Path.stat

    def flaky_stat(self, *a, **kw):
        if self.name == "gone.jsonl":
            raise FileNotFoundError(str(self))
        return real_stat(self, *a, **kw)

    pathlib.Path.stat = flaky_stat
    try:
        out = Controller.list_sessions(SimpleNamespace(cwd=cwd, state_dir=root))
    finally:
        pathlib.Path.stat = real_stat
    ctx.check(f"only the surviving session is listed, got {[s['id'] for s in out]}", [s["id"] for s in out] == ["keep"])


@test
def test_item74_typed_sgr_literal_after_a_clipboard_paste_survives(ctx: Ctx):
    async def body():
        fake, app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            pi = app.prompt_input
            pi.focus()
            pi.paste_text(r"echo '\e[1;32m")
            for key in ("space", "o", "k", "m"):
                await pilot.press(key)
            await pilot.pause(0.05)
            ctx.check(f"nothing was stripped, got {pi.text!r}", pi.text == r"echo '\e[1;32m okm")
            pi.text = "hi "
            pi.move_cursor(pi.document.end)
            for ch in "<35;72;18M":
                await pilot.press({"<": "less_than_sign", ";": "semicolon"}.get(ch, ch))
            await pilot.pause(0.05)
            ctx.check(f"a report typed at the cursor still goes, got {pi.text!r}", pi.text == "hi ")
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
