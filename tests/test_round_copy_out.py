"""tests.test_round_copy_out -- Halo 2.0.7: the copy-out fix (rolo
2026-10-07: "copying text from the session to another file seems to not
really work well").

The contract:
  * a PARTIAL transcript selection copies exactly the dragged RANGE
    (Selection.extract over the widget's stored source) -- a grazing
    drag no longer copies half the screen;
  * a WHOLE-widget selection keeps the stored-source path (cleaned,
    chrome-stripped) unchanged;
  * every EXPLICIT copy (perform_copy) confirms with the mechanism that
    actually landed -- "Copy verified via system clipboard (N
    characters)" from the external-tool floor, or a visible failure
    warning naming the install hint when nothing landed;
  * the read direction strips ONE leading BOM;
  * doctor's clipboard line states the full path verdict.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

REPO_DIR = Path(__file__).resolve().parent.parent

test, TESTS = new_registry()


class _Env:
    def __init__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        d = tempfile.mkdtemp(prefix="copyout-")
        os.environ["BRIDGE_TEST_HOME"] = d
        os.environ["BRIDGE_STATE_DIR"] = d

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


def _run(coro):
    return asyncio.run(coro)


# ---- range-narrowed selection copies ---------------------------------------------


@test
def test_partial_selection_copies_the_dragged_range(ctx: Ctx):
    from textual.selection import Offset, Selection
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    from halo_harness.tui.widgets.transcript import SystemNote

    async def body():
        with _Env():
            fake = FakeController()
            app = BridgeApp(fake, cwd=str(REPO_DIR))
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.3)
                note = SystemNote("line zero\nline one\nline two\nline three", kind="note")
                await app.transcript.mount(note)
                await pilot.pause(0.1)
                # Drag from (line 1, x 0) to (line 2, x 8): exactly
                # "line one" + "line two" -- NOT the whole widget.
                # Textual's Offset is (x, y) = (column, line).
                app.screen.selections = {note: Selection(Offset(0, 1), Offset(8, 2))}
                got = app._selected_transcript_text()
                ctx.check(f"a partial drag copies exactly the range, got {got!r}",
                          got is not None and "line one" in got and "line two" in got)
                ctx.check("the untouched lines are NOT in the copy",
                          got is not None and "line zero" not in got and "line three" not in got)
                # A WHOLE-widget selection keeps the full source path.
                app.screen.selections = {note: Selection(None, None)}
                got2 = app._selected_transcript_text()
                ctx.check(f"a whole-widget selection copies all four lines, got {got2!r}",
                          got2 is not None and all(f"line {w}" in got2 for w in ("zero", "one", "two", "three")))
    _run(body())


# ---- the confirmed copy with mechanism verdict --------------------------------------


@test
def test_perform_copy_confirms_the_landing_mechanism(ctx: Ctx):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp

    async def body():
        with _Env():
            import halo_harness.tui.clipboard as clipboard_mod
            real_copy_tool = clipboard_mod.copy_via_external_tool
            real_trusted = clipboard_mod.osc52_trusted
            fake = FakeController()
            app = BridgeApp(fake, cwd=str(REPO_DIR))
            notes = []
            app.notify = lambda msg, **kw: notes.append((msg, kw.get("severity")))
            try:
                async with app.run_test(size=(100, 30)) as pilot:
                    # The external tool lands -> the worker posts the verified line.
                    clipboard_mod.copy_via_external_tool = lambda *a, **kw: True
                    clipboard_mod.osc52_trusted = lambda *a, **kw: False
                    ok = app.perform_copy("hello copy world", label="this turn")
                    ctx.check("perform_copy reports success", ok is True)
                    await app.workers.wait_for_complete()
                    ctx.check(f"the immediate line names the label, got {notes}",
                              any("Copied this turn" in m for m, _s in notes))
                    ctx.check("the verified line names the system clipboard",
                              any("Copy verified via system clipboard" in m for m, _s in notes))
                    notes.clear()
                    # Nothing lands and OSC 52 is untrusted -> a visible ERROR.
                    clipboard_mod.copy_via_external_tool = lambda *a, **kw: False
                    ok2 = app.perform_copy("second try", label="this turn")
                    ctx.check("perform_copy still returns True (OSC 52 may yet land)", ok2 is True)
                    await app.workers.wait_for_complete()
                    ctx.check(f"a total failure is a visible warning, got {notes}",
                              any("Copy FAILED" in m and s == "error" for m, s in notes))
            finally:
                clipboard_mod.copy_via_external_tool = real_copy_tool
                clipboard_mod.osc52_trusted = real_trusted
    _run(body())


# ---- the BOM strip on the read direction ---------------------------------------------


@test
def test_read_strips_one_leading_bom(ctx: Ctx):
    import subprocess
    from halo_harness.tui import clipboard as clipboard_mod

    calls = {}

    def fake_run(argv, **kw):
        calls["argv"] = argv
        return subprocess.CompletedProcess(argv, 0,
                                           stdout=chr(0xFEFF).encode("utf-8") + b"BOM-prefixed text\n",
                                           stderr=b"")

    real_run = subprocess.run
    subprocess.run = fake_run
    try:
        out = clipboard_mod.read_via_external_tool(platform="win32")
    finally:
        subprocess.run = real_run
    ctx.check(f"the BOM is stripped, got {out!r}", out == "BOM-prefixed text")
    ctx.check("exactly ONE BOM went (never a second strip of real content)",
              not (out or "").startswith(chr(0xFEFF)))


# ---- doctor's line ---------------------------------------------------------------------


@test
def test_doctor_clipboard_line_states_the_path_verdict(ctx: Ctx):
    from halo_harness.tui.clipboard import clipboard_doctor_line
    win = clipboard_doctor_line(platform="win32")
    ctx.check("win32 names both directions + the range behavior",
              "write:" in win and "read:" in win and "dragged range" in win)
    mac = clipboard_doctor_line(platform="darwin")
    ctx.check("darwin too", "write:" in mac and "read:" in mac)
    # Linux WITH a tool vs WITHOUT.
    import halo_harness.tui.clipboard as cm
    real_find = cm.find_clipboard_tool
    cm.find_clipboard_tool = lambda: ("xclip", ["xclip", "-selection", "clipboard"])
    try:
        linux_ok = clipboard_doctor_line(platform="linux")
    finally:
        cm.find_clipboard_tool = real_find
    ctx.check("linux with a tool is OK and names the floor",
              linux_ok.startswith("[OK]") and "xclip floor" in linux_ok)
    cm.find_clipboard_tool = lambda: None
    try:
        linux_warn = clipboard_doctor_line(platform="linux")
    finally:
        cm.find_clipboard_tool = real_find
    ctx.check("linux without a tool is a WARN naming the install hint",
              linux_warn.startswith("[WARN]") and "xclip/wl-copy/xsel" in linux_warn)


# ---- the tmux/Kali case (rolo 2026-10-08: "copying from kali is not working") -----


@test
def test_tmux_drops_osc52_until_enabled(ctx: Ctx):
    from halo_harness.tui import clipboard as cm
    # Not in tmux at all -> trusted on Linux, as before.
    ctx.check("no tmux -> OSC 52 trusted on linux",
              cm.osc52_trusted({"TERM": "xterm"}, platform="linux") is True)
    # In tmux with set-clipboard off (the default): tmux eats the sequence,
    # so OSC 52 is NOT trusted, and the doctor/confirm lines name the fix.
    # (No real tmux binary needed: the query failure itself reads as 'off'.)
    cm._TMUX_MODE_CACHE.clear()
    ctx.check("tmux present, set-clipboard off -> untrusted",
              cm.osc52_trusted({"TMUX": "/tmp/tmux-1000/default,123,0"}, platform="linux") is False)
    mode = cm.tmux_clipboard_mode({"TMUX": "/tmp/tmux-1000/default,123,0"})
    ctx.check(f"the mode reads as off (conservative), got {mode!r}", mode == "off")
    line = cm.clipboard_doctor_line({"TMUX": "/tmp/tmux-1000/default,123,0"}, platform="linux")
    ctx.check(f"doctor WARNs with the one-line fix, got {line!r}",
              line.startswith("[WARN]") and "set-clipboard on" in line)
    # set-clipboard on -> tmux relays, trusted again.
    cm._TMUX_MODE_CACHE["/tmp/tmux-1000/on,1,0"] = "on"
    ctx.check("tmux with set-clipboard on -> trusted",
              cm.osc52_trusted({"TMUX": "/tmp/tmux-1000/on,1,0"}, platform="linux") is True)
    cm._TMUX_MODE_CACHE.clear()


@test
def test_copy_failure_names_the_tmux_fix(ctx: Ctx):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp

    async def body():
        with _Env():
            import halo_harness.tui.clipboard as clipboard_mod
            fake = FakeController()
            app = BridgeApp(fake, cwd=str(REPO_DIR))
            notes = []
            app.notify = lambda msg, **kw: notes.append((msg, kw.get("severity")))
            async with app.run_test(size=(100, 30)) as pilot:
                clipboard_mod.copy_via_external_tool = lambda *a, **kw: False
                # In tmux (mode cached 'off'): the failure names the fix.
                clipboard_mod._TMUX_MODE_CACHE.clear()
                clipboard_mod._TMUX_MODE_CACHE["tm"] = "off"
                real_mode = clipboard_mod.tmux_clipboard_mode
                real_trusted_fn = clipboard_mod.osc52_trusted
                clipboard_mod.tmux_clipboard_mode = lambda env=None: "off"
                try:
                    app.perform_copy("kali copy", label="this turn")
                    await app.workers.wait_for_complete()
                    ctx.check(f"the failure names the tmux fix, got {notes}",
                              any("tmux" in m and "set-clipboard on" in m and s == "error"
                                  for m, s in notes))
                    notes.clear()
                    # NOT in tmux: the generic failure line, no tmux mention.
                    # (osc52_trusted stubbed False so the branch is
                    # deterministic regardless of THIS host's terminal.)
                    clipboard_mod.tmux_clipboard_mode = lambda env=None: None
                    clipboard_mod.osc52_trusted = lambda *a, **kw: False
                    app.perform_copy("kali copy 2", label="this turn")
                    await app.workers.wait_for_complete()
                    ctx.check(f"no-tmux failure stays generic, got {notes}",
                              any("Copy FAILED" in m and "tmux" not in m for m, _s in notes))
                finally:
                    clipboard_mod.tmux_clipboard_mode = real_mode
                    clipboard_mod.osc52_trusted = real_trusted_fn
                    clipboard_mod._TMUX_MODE_CACHE.clear()
    _run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
