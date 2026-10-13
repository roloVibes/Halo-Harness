"""tests.test_input_hygiene -- Halo 3.0.2.0: terminal mouse reports stay out
of the prompt, and the prompt has a clear key.

- `win32_input.keep_key_record`: a synthetic record (virtual-key 0) is kept
  under NumLock/CapsLock/Shift and dropped only while Alt or Ctrl is held;
  an empty character is never kept. `install()` is a no-op off Windows and
  patches Textual's monitor class once on it.
- `input_sanitize.strip_mouse_reports`: whole reports and cut tails go,
  ordinary text with numbers stays.
- The widget: typing a report's final `M` drops the fragment; a paste is
  kept as pasted; Ctrl+U empties the box; Esc empties it when no turn runs.

Run: python -m tests.test_input_hygiene
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from halo_harness.tui.win32_input import ALT_OR_CTRL, PendingInput, drop_orphan_tails, install, keep_key_record  # noqa: E402
from halo_harness.tui.widgets.input_sanitize import looks_like_mouse_report, strip_mouse_reports  # noqa: E402

test, TESTS = new_registry()

NUMLOCK, CAPSLOCK, SHIFT, LEFT_CTRL, LEFT_ALT = 0x20, 0x80, 0x10, 0x08, 0x02


@test
def test_lock_keys_never_drop_a_synthetic_record(ctx: Ctx):
    ctx.check("ESC with vkey 0 under NumLock is kept", keep_key_record("\x1b", 0, NUMLOCK))
    ctx.check("ESC with vkey 0 under CapsLock+NumLock is kept", keep_key_record("\x1b", 0, NUMLOCK | CAPSLOCK))
    ctx.check("a shifted synthetic char is kept", keep_key_record("<", 0, SHIFT))
    ctx.check("a plain record with a real vkey is kept", keep_key_record("a", 0x41, NUMLOCK))
    ctx.check("vkey 0 with Ctrl held is dropped", not keep_key_record("\x00", 0, LEFT_CTRL))
    ctx.check("vkey 0 with Alt held is dropped", not keep_key_record("x", 0, LEFT_ALT | NUMLOCK))
    ctx.check("an empty character is never kept", not keep_key_record("", 0x41, 0))
    ctx.check("the modifier mask is exactly the four Alt/Ctrl bits", ALT_OR_CTRL == 0x0F)


@test
def test_install_is_a_no_op_off_windows_and_idempotent_on_it(ctx: Ctx):
    first = install()
    second = install()
    if sys.platform == "win32":
        from textual.drivers import win32
        ctx.check("installed on Windows", first is True and second is True)
        ctx.check("Textual's monitor class is the patched subclass", getattr(win32.EventMonitor, "_halo_patched", False))
        ctx.check("the patched class keeps Textual's signature", win32.EventMonitor.__init__ is win32.EventMonitor.__mro__[1].__init__)
    else:
        ctx.check("a no-op off Windows", first is False and second is False)


def _replay(batches, *, pending: bool, gap_s: float = 0.15):
    """Feed batches to Textual's real parser the way the input thread
    does, with a quiet gap (longer than ESCDELAY) between them."""
    import time
    from textual._xterm_parser import XTermParser
    parser = XTermParser()
    stage = PendingInput()
    out = []
    for i, batch in enumerate(batches):
        if i:
            time.sleep(gap_s)
            out.extend(parser.tick())
            if pending and stage.held:
                pass  # the thread keeps waiting (30 ms polls) while it holds a tail
        text = stage.push(batch) if pending else batch
        if text:
            out.extend(parser.feed(text))
    if pending and stage.held:
        out.extend(parser.feed(stage.flush()))
    time.sleep(gap_s)
    out.extend(parser.tick())
    return [(type(e).__name__, getattr(e, "key", None)) for e in out]


@test
def test_a_report_split_across_two_reads_never_becomes_text(ctx: Ctx):
    split = ["\x1b[<35;72;1", "8M"]
    raw = _replay(split, pending=False)
    ctx.check(f"Textual alone types the whole report after the escape delay (the bug), got {raw}",
              ("Key", "M") in raw and ("Key", "left_square_bracket") in raw and not any(n == "MouseMove" for n, _k in raw))
    fixed = _replay(split, pending=True)
    ctx.check(f"with the pending stage it is one mouse move, got {fixed}", fixed == [("MouseMove", None)])
    lone = _replay(["\x1b[<35;1;1M", "\x1b"], pending=True)
    ctx.check(f"a real Esc after a report still arrives, got {lone}", lone == [("MouseMove", None), ("Key", "escape")])
    stage = PendingInput()
    ctx.check("a paste ending in text is not held", stage.push("\x1b[200~3;4M\x1b[201~") == "\x1b[200~3;4M\x1b[201~" and not stage.held)
    ctx.check("an incomplete CSI is held", stage.push("ab\x1b[") == "ab" and stage.held == "\x1b[")
    ctx.check("and released with the rest", stage.push("<0;3;4M") == "\x1b[<0;3;4M" and not stage.held)


@test
def test_orphan_report_tails_are_dropped_before_the_parser(ctx: Ctx):
    for tail in ("[<35;72;18M", "8;17M", ";93;17M", "19;19M129;23M", "[<35;115;19M19;19M"):
        ctx.check(f"a batch of tails is dropped: {tail!r}", drop_orphan_tails(tail) == "")
    report = "\x1b[<35;10;5M"
    ctx.check("tails beside complete reports leave the reports", drop_orphan_tails(report + "8;17M" + report) == report + report)
    for keep in ("M", "m", "a", "3", ";", "x;1M", "hello", report + "a", "\x1b[200~3;4M\x1b[201~", "\x1b[A"):
        ctx.check(f"typed text survives: {keep!r}", drop_orphan_tails(keep) == keep)


@test
def test_strip_mouse_reports(ctx: Ctx):
    # Two-number tails cut from a report ("8;17M") are dropped before the
    # parser by win32_input.drop_orphan_tails; here only the report shape goes.
    leaked = "[<35;72;18M<35;115;19M 35;72;18M"
    ctx.check("a leaked burst is recognised", looks_like_mouse_report(leaked))
    ctx.check(f"a leaked burst strips to a space, got {strip_mouse_reports(leaked)!r}", strip_mouse_reports(leaked) == " ")
    ctx.check("a release report strips too", strip_mouse_reports("hi [<0;10;5m there") == "hi  there")
    for keep in ("fix the bug in model.py", "sum of 3 and 4", "version 2.0.11", "M=3; N=4", "at 10:30",
                 r"fix this script: printf '\033[1;31mERROR\033[0m'", r"echo '\e[1;32m okm",
                 r"PS1='\[\e[0;32m\]\u@\h\$ '", r"echo -e '\e[1;31;40mred'", "move 12;34M"):
        ctx.check(f"ordinary text survives: {keep!r}", strip_mouse_reports(keep) == keep and not looks_like_mouse_report(keep))


def _app():
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project")


@test
def test_prompt_strips_typed_fragments_and_clears_on_ctrl_u_and_esc(ctx: Ctx):
    async def body():
        app = _app()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.2)
            pi = app.prompt_input
            pi.focus()
            pi.text = "hello "
            pi.move_cursor(pi.document.end)
            for ch in "[<35;72;18M":
                await pilot.press(ch if ch not in ("[", "<", ";") else {"[": "left_square_bracket", "<": "less_than_sign", ";": "semicolon"}[ch])
            await pilot.pause(0.05)
            ctx.check(f"the typed report is gone, got {pi.text!r}", pi.text == "hello ")
            await pilot.press("ctrl+u")
            await pilot.pause(0.05)
            ctx.check(f"Ctrl+U empties the box, got {pi.text!r}", pi.text == "")
            pi.text = "a draft"
            await pilot.press("escape")
            await pilot.pause(0.05)
            ctx.check(f"Esc with nothing running empties the box, got {pi.text!r}", pi.text == "")
            from textual.events import Paste
            pi.text = ""
            pi.post_message(Paste("plan [<35;1;2M the work"))
            await pilot.pause(0.1)
            ctx.check(f"a paste is kept exactly as pasted, got {pi.text!r}", pi.text == "plan [<35;1;2M the work")
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    print_results(results, passed, failed, skipped)
    sys.exit(1 if failed else 0)
