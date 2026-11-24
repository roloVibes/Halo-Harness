"""tests.test_console_mode -- Halo 2.0.7 round 7c, deliverable 1: on a Windows
console Ctrl+C must reach the TUI only as a key. The helper is driven here
against a fake kernel32 (and a fake signal module), never a real console.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

PROCESSED = 0x0001
VT_INPUT = 0x0200
HANDLE = 7


class FakeKernel32:
    def __init__(self, mode: int, console: bool = True):
        self.mode = mode
        self.console = console
        self.handlers: list = []
        self.set_calls: list = []

    def GetStdHandle(self, which):
        self.which = which
        return HANDLE

    def GetConsoleMode(self, handle, ptr):
        if not self.console or handle != HANDLE:
            return 0
        ptr.contents.value = self.mode
        return 1

    def SetConsoleMode(self, handle, mode):
        self.set_calls.append(mode)
        self.mode = mode
        return 1

    def SetConsoleCtrlHandler(self, fn, add):
        if add:
            self.handlers.append(fn)
        else:
            self.handlers.remove(fn)
        return 1


class FakeSignal:
    SIGINT = 2
    SIG_IGN = "ignore"

    def __init__(self):
        self.current = "original"

    def getsignal(self, sig):
        return self.current

    def signal(self, sig, handler):
        self.current = handler


def _install(k32, sig=None):
    from halo_harness.tui import console_mode
    return console_mode.install(kernel32=k32, platform="win32", signal_module=sig)


@test
def test_install_clears_processed_input_and_restore_puts_it_back(ctx: Ctx):
    k32 = FakeKernel32(PROCESSED | VT_INPUT)
    guard = _install(k32)
    ctx.check("guard is active", guard.active)
    ctx.check("ENABLE_PROCESSED_INPUT cleared", not k32.mode & PROCESSED)
    ctx.check("the other flags are kept", bool(k32.mode & VT_INPUT))
    ctx.check("the stdin handle was requested (-10)", k32.which == -10)
    guard.restore()
    ctx.check(f"original mode restored, got {k32.mode:#x}", k32.mode == PROCESSED | VT_INPUT)
    ctx.check("handler removed", k32.handlers == [])
    guard.restore()  # idempotent
    ctx.check("second restore is harmless", k32.mode == PROCESSED | VT_INPUT)


@test
def test_handler_swallows_ctrl_c_event_only(ctx: Ctx):
    k32 = FakeKernel32(PROCESSED)
    guard = _install(k32)
    ctx.check("one control handler registered", len(k32.handlers) == 1)
    handler = k32.handlers[0]
    ctx.check("CTRL_C_EVENT (0) is handled", bool(handler(0)))
    ctx.check("CTRL_BREAK_EVENT (1) is left alone", not handler(1))
    ctx.check("CTRL_CLOSE_EVENT (2) is left alone", not handler(2))
    guard.restore()


@test
def test_reassert_clears_a_flag_something_else_switched_back_on(ctx: Ctx):
    k32 = FakeKernel32(VT_INPUT)
    guard = _install(k32)
    ctx.check("nothing to fix yet", guard.reassert() is False)
    k32.mode |= PROCESSED  # a child console process restored a stale mode
    ctx.check("reassert reports it fixed something", guard.reassert() is True)
    ctx.check("processed input is off again", not k32.mode & PROCESSED)
    guard.restore()
    ctx.check("reassert after restore does nothing", guard.reassert() is False)


@test
def test_sigint_is_ignored_while_installed_and_restored_after(ctx: Ctx):
    sig = FakeSignal()
    k32 = FakeKernel32(PROCESSED)
    guard = _install(k32, sig)
    ctx.check("SIGINT ignored while the TUI runs", sig.current == "ignore")
    guard.restore()
    ctx.check("SIGINT disposition restored", sig.current == "original")


@test
def test_no_console_attached_still_installs_the_handler_safely(ctx: Ctx):
    k32 = FakeKernel32(0, console=False)
    guard = _install(k32)
    ctx.check("no mode change attempted", k32.set_calls == [])
    ctx.check("handler still registered", len(k32.handlers) == 1)
    guard.restore()
    ctx.check("restore does not touch the mode it never read", k32.set_calls == [])


@test
def test_posix_is_a_no_op(ctx: Ctx):
    from halo_harness.tui import console_mode
    k32 = FakeKernel32(PROCESSED)
    sig = FakeSignal()
    guard = console_mode.install(kernel32=k32, platform="linux", signal_module=sig)
    ctx.check("guard inert", guard.active is False)
    ctx.check("mode untouched", k32.mode == PROCESSED and k32.set_calls == [])
    ctx.check("no handler", k32.handlers == [])
    ctx.check("SIGINT untouched", sig.current == "original")
    ctx.check("reassert/restore are harmless", guard.reassert() is False and guard.restore() is None)


@test
def test_a_failing_kernel32_never_raises(ctx: Ctx):
    class Broken(FakeKernel32):
        def SetConsoleCtrlHandler(self, fn, add):
            raise OSError("no console")
    k32 = Broken(PROCESSED)
    guard = _install(k32)
    ctx.check("returns an inert guard", guard.active is False)
    ctx.check("the mode it changed was put back", k32.mode == PROCESSED)


@test
def test_launcher_installs_and_restores_the_guard(ctx: Ctx):
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "tui" / "launch.py").read_text(encoding="utf-8")
    ctx.check("run_tui installs the guard before app.run", src.index("console_mode.install()") < src.index("app.run()"))
    ctx.check("run_tui restores it in the finally", "console_guard.restore()" in src)


@test
def test_a_ctrl_c_event_the_console_made_from_a_key_is_handed_to_the_app_as_the_key(ctx: Ctx):
    """3.6.0.18 K: a child (a `.cmd`'s cmd.exe) switched processed input back on, so the console made the person's
    Ctrl+C press a CTRL_C_EVENT: the app gets ONE Ctrl+C key and the flag is cleared at once. With the flag off the
    event was a program's (GenerateConsoleCtrlEvent): swallowed, nothing else."""
    k32 = FakeKernel32(VT_INPUT)
    guard = _install(k32)
    calls: list = []
    try:
        handler = k32.handlers[0]
        guard.on_ctrl_c = lambda: calls.append("key")
        k32.mode |= PROCESSED  # what a `.cmd` child leaves behind
        ctx.check("the event is handled (the process never ends by it)", bool(handler(0)))
        ctx.check(f"the app got ONE Ctrl+C key, got {calls}", calls == ["key"])
        ctx.check(f"processed input is cleared at once, mode {k32.mode:#x}", not k32.mode & PROCESSED)
        ctx.check("the other flags are kept", bool(k32.mode & VT_INPUT))
        ctx.check("an event with the flag off (a program's) is swallowed", bool(handler(0)))
        ctx.check(f"... and hands the app nothing, got {calls}", calls == ["key"])

        def boom():
            raise RuntimeError("the app is gone")
        guard.on_ctrl_c = boom
        k32.mode |= PROCESSED
        ctx.check("a callable that raises is swallowed: still handled", bool(handler(0)))
        ctx.check("... and the flag is still cleared", not k32.mode & PROCESSED)
        guard.on_ctrl_c = None
        k32.mode |= PROCESSED
        ctx.check("no callable yet (the app not up): handled, nothing else", bool(handler(0)))
        ctx.check("CTRL_BREAK_EVENT (1) is left alone as before", not handler(1))
    finally:
        guard.restore()


@test
def test_the_launchers_hand_posts_one_ctrl_c_key_the_app_routes_as_the_key(ctx: Ctx):
    """tui/launch.py's `post_ctrl_c_key`, from another thread (the console's handler thread), reaches the app's own
    ctrl+c binding once, through the driver; nothing when the app has no driver."""
    import asyncio
    import threading
    from textual.app import App
    from halo_harness.tui.launch import post_ctrl_c_key

    class One(App):
        BINDINGS = [("ctrl+c", "count", "count")]
        hits = 0

        def action_count(self) -> None:
            self.hits += 1

    app = One()
    post_ctrl_c_key(app)  # no driver yet: nothing, no error

    async def drive():
        async with app.run_test() as pilot:
            t = threading.Thread(target=post_ctrl_c_key, args=(app,))
            t.start()
            t.join(30)
            for _ in range(200):
                if app.hits:
                    break
                await pilot.pause(0.05)
            await pilot.pause()
    asyncio.run(drive())
    ctx.check(f"the app's ctrl+c binding ran once, got {app.hits}", app.hits == 1)
    # Textual keeps `_driver` after the app has run: run_tui takes the hand away the moment app.run() returns, before
    # the way out (join_the_pool) and long before the guard is restored, so no key is posted to a closed loop
    src = (Path(__file__).resolve().parent.parent / "halo_harness" / "tui" / "launch.py").read_text(encoding="utf-8")
    run, gone, join = (src.find("app.run()"), src.find("console_guard.on_ctrl_c = None"),
                       src.find("join_the_pool(app)"))
    ctx.check("run_tui clears the guard's hand after app.run() and before the way out", 0 <= run < gone < join)


# -- Windows only: a real pseudoconsole (scripts/realcheck/conpty.py) --------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
_K32_MODE = ("import ctypes\nk32 = ctypes.windll.kernel32\nh = k32.GetStdHandle(-10)\n"
             "def mode():\n    m = ctypes.c_uint32(0)\n    k32.GetConsoleMode(h, ctypes.byref(m))\n    return m.value\n")
_GUARD_CHILD = (f"import sys, os, time\nsys.path.insert(0, {str(REPO)!r})\n" + _K32_MODE +
                "from halo_harness.tui import console_mode\n"
                "out = sys.argv[1]\n"
                "guard = console_mode.install(write=lambda s: None)\n"
                "def key():\n    with open(out, 'a') as f:\n        f.write('ctrl+c key\\n')\n"
                "guard.on_ctrl_c = key\n"
                "k32.SetConsoleMode(h, mode() | 1)\n"  # processed input ON: what a `.cmd` child leaves behind
                "print('READY', flush=True)\n"
                "end = time.monotonic() + 120\n"
                "while time.monotonic() < end and not os.path.exists(out):\n    time.sleep(0.05)\n")
_CMD_CHILD = (f"import sys\nsys.path.insert(0, {str(REPO)!r})\n" + _K32_MODE +
              "from halo_harness import subprocess_safe\n"
              "k32.SetConsoleMode(h, (mode() & ~1) | 0x200)\n"  # as the terminal app's reader leaves it
              "switch = getattr(subprocess_safe, 'set_terminal_app', None)\n"
              "if switch:\n    switch(True)\n"
              "r = subprocess_safe.run([sys.argv[1]], capture_output=True, timeout=120)\n"
              "print(f'RAN={r.returncode} MODE={mode():#x} END', flush=True)\n")


def _in_pseudoconsole(script: str, *args):
    """(terminal, restore): `script` run by this Python in a fresh pseudoconsole; `restore()` ends it and puts back
    what the pseudoconsole changed in this process (sys.path; Ctrl+C ignored or not)."""
    import ctypes
    import os
    sys.path.insert(0, str(REPO / "scripts"))
    from realcheck import winproc
    from realcheck.conpty import ConPtyTerminal
    flags = winproc.console_flags(os.getpid())
    ignored = bool(flags is not None and flags & winproc.IGNORE_CTRL_C)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", HALO_NO_UPDATER="1", OLLAMA_HOST="http://127.0.0.1:9")
    term = ConPtyTerminal([sys.executable, "-I", "-c", script, *args], env=env, cwd=str(REPO))

    def restore():
        try:
            if term.poll() is None:
                term.hard_kill()
            term.wait(30)
            term.cleanup()
        finally:
            if ignored:  # the pseudoconsole cleared "Ctrl+C is ignored" on this process: put it back
                k = ctypes.WinDLL("kernel32")
                k.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, ctypes.c_int]
                k.SetConsoleCtrlHandler(None, 1)
            sys.path.remove(str(REPO / "scripts"))
    return term, restore


@test
def test_windows_a_typed_ctrl_c_under_processed_input_reaches_the_app_as_one_key(ctx: Ctx):
    """Red on 3.6.0.17: the guard swallowed the event the console made of the typed key, and nothing else happened."""
    if sys.platform != "win32":
        from tests.helpers.runner import SkipTest
        raise SkipTest("the console's processed input and its CTRL_C_EVENT are Windows's")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "keys.txt"
        term, restore = _in_pseudoconsole(_GUARD_CHILD, str(out))
        try:
            ctx.check("the child installed the guard and said READY", term.wait_for(lambda s: "READY" in s, 60))
            term.ctrl_c()  # the byte 0x03, once
            end = __import__("time").monotonic() + 60
            while not out.exists() and term.poll() is None and __import__("time").monotonic() < end:
                __import__("time").sleep(0.05)
            got = out.read_text().count("ctrl+c key") if out.exists() else 0
            ctx.check(f"the guard's callable ran once for the one typed Ctrl+C, got {got}", got == 1)
        finally:
            restore()


@test
def test_windows_a_cmd_child_started_while_the_app_is_up_leaves_processed_input_off(ctx: Ctx):
    """Red on 3.6.0.17: the `.cmd` child inherited the console's input and its cmd.exe left processed input ON."""
    if sys.platform != "win32":
        from tests.helpers.runner import SkipTest
        raise SkipTest("a `.cmd` child and the console input mode are Windows's")
    import re
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        cmd = Path(d) / "stand-in.cmd"
        cmd.write_text("@echo off\r\necho stand-in\r\n", encoding="ascii")
        term, restore = _in_pseudoconsole(_CMD_CHILD, str(cmd))
        try:
            ctx.check("the child ran the .cmd and printed the mode", term.wait_for(lambda s: "END" in s, 120))
            m = re.search(r"RAN=(\d+) MODE=(0x[0-9a-f]+)", term.plain())
            mode = int(m.group(2), 16) if m else None
            ctx.check(f"the .cmd ran, got {m.group(0) if m else term.plain()[-200:]!r}", bool(m) and m.group(1) == "0")
            ctx.check(f"processed input is still OFF after it, mode {mode if mode is None else hex(mode)}",
                      mode is not None and not mode & PROCESSED)
        finally:
            restore()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
