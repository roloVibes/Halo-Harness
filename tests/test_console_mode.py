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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
