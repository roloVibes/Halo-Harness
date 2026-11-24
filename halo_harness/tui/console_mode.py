"""halo_harness.tui.console_mode -- the Windows console never kills the TUI.

Why this exists (rolo 2026-10-09, "when I press Ctrl+C once in a Halo
session in PowerShell, it closes"). On a Windows console a Ctrl+C press can
reach a process two ways: as the key character 0x03 (what the app's
`ctrl+c` binding wants) or as a CONSOLE CONTROL EVENT (`CTRL_C_EVENT`),
which the C runtime turns into SIGINT / KeyboardInterrupt in the main
thread -- the event path ends the process before Textual sees any key. The
console only generates that event while `ENABLE_PROCESSED_INPUT` is set on
the console INPUT handle, and the flag does not stay put: any console
process sharing the window (the PowerShell the clipboard helper starts,
`git`, a tool a model runs) may save and restore the input mode around its
own work, and a stale restore switches processed input back on in the
middle of a Halo session.

`install()` therefore does two independent things for the TUI's lifetime:
  1. clears `ENABLE_PROCESSED_INPUT` on the input handle (and `reassert()`
     clears it again if something flipped it back -- the app calls that on
     a timer), so Ctrl+C is only ever a key;
  2. registers a control handler that takes every `CTRL_C_EVENT` (and tells
     the C runtime's SIGINT to stand down), so no event ends the session.
     When processed input is ON at that moment, a child switched it back on
     (a `.cmd`'s cmd.exe does as it leaves) and the console made the
     person's key press this event (3.6.0.18 K): the handler clears the flag
     at once and hands the app ONE Ctrl+C key through `Guard.on_ctrl_c`
     (tui/launch.py sets it once the app exists; it posts the key the way
     the Windows driver's reader thread posts its events). When the flag is
     OFF the event was a program's (`GenerateConsoleCtrlEvent`): swallowed,
     nothing else.
`Guard.restore()` puts the saved mode back, removes the handler and the
SIGINT disposition; the launcher calls it from a `finally`, and an
`atexit` hook covers a crash that skips it. A CTRL_BREAK still ends the
process (the default handler runs after this one), but first the handler
writes off what the full-screen session switched on -- the alternate
screen, mouse reporting, bracketed paste, the hidden cursor -- and puts the
saved input mode back: the session's own exit, which normally does that,
never runs (3.6.0.0 fx). Close and logoff events are untouched. On POSIX `install()` returns an inert guard: SIGINT
keeps the behaviour Textual already gives the app. Print mode (`halo -p`)
never calls this, so SIGINT = exit 130 there is unchanged.

The kernel32 object, the platform string and the signal module are
parameters so the unit tests drive a fake instead of a real console.
"""

from __future__ import annotations

import atexit
import ctypes
import os
import sys
from typing import Any, Optional

ENABLE_PROCESSED_INPUT = 0x0001
STD_INPUT_HANDLE = -10
CTRL_C_EVENT = 0
CTRL_BREAK_EVENT = 1
# What a full-screen session turns on and its own exit turns off again (mouse reporting in all its modes, bracketed
# paste, the cursor, the alternate screen last so the shell's prompt comes back on the main screen).
TERMINAL_RESET = "\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[?1015l\x1b[?2004l\x1b[?25h\x1b[?1049l"


def _write_terminal(text: str) -> None:
    out = getattr(sys, "__stdout__", None)
    os.write(out.fileno() if out is not None else 1, text.encode("ascii"))


def _real_kernel32() -> Any:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    from ctypes import wintypes
    k32.GetStdHandle.argtypes = [wintypes.DWORD]
    k32.GetStdHandle.restype = wintypes.HANDLE
    k32.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.GetConsoleMode.restype = wintypes.BOOL
    k32.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k32.SetConsoleMode.restype = wintypes.BOOL
    k32.SetConsoleCtrlHandler.argtypes = [_handler_type(), wintypes.BOOL]
    k32.SetConsoleCtrlHandler.restype = wintypes.BOOL
    return k32


def _handler_type() -> Any:
    """`WINFUNCTYPE(BOOL, DWORD)` on Windows; identity elsewhere (a fake
    kernel32 under test just stores the plain Python callable)."""
    factory = getattr(ctypes, "WINFUNCTYPE", None)
    if factory is None:
        return lambda fn: fn
    from ctypes import wintypes
    return factory(wintypes.BOOL, wintypes.DWORD)


class Guard:
    """What `install()` did, so it can be undone. Inert (`active` False)
    on POSIX or when no console is attached."""

    def __init__(self, k32: Any = None, handle: Any = None, saved_mode: Optional[int] = None,
                 handler: Any = None, signal_module: Any = None, saved_sigint: Any = None,
                 write: Any = None) -> None:
        self._k32 = k32
        self._handle = handle
        self._saved_mode = saved_mode
        self._handler = handler  # keep a reference: a collected callback crashes the process
        self._signal = signal_module
        self._saved_sigint = saved_sigint
        self.active = k32 is not None
        self._restored = False
        self._write = write  # the terminal's writer (a real run only; a fake console never writes to the tests' own)
        self.on_ctrl_c = None  # 3.6.0.18 K: hands the app one Ctrl+C key (tui/launch.py sets it)

    def ctrl_c_event(self) -> None:
        """A CTRL_C_EVENT: the console made it from a key press when processed input is on now (a child switched it
        back on): the flag is cleared and the app gets the key. A program's event (flag off) is only swallowed."""
        if not self.reassert():
            return
        hand = self.on_ctrl_c
        if hand is not None:
            hand()

    def _mode(self) -> Optional[int]:
        if self._k32 is None or self._handle is None:
            return None
        value = ctypes.c_uint32(0)
        ptr = ctypes.pointer(value)
        if not self._k32.GetConsoleMode(self._handle, ptr):
            return None
        return int(ptr.contents.value)

    def reassert(self) -> bool:
        """Clear ENABLE_PROCESSED_INPUT again if something set it. Returns
        True when it had to. Cheap and non-blocking (two kernel32 calls)."""
        if not self.active or self._restored:
            return False
        mode = self._mode()
        if mode is None or not mode & ENABLE_PROCESSED_INPUT:
            return False
        self._k32.SetConsoleMode(self._handle, mode & ~ENABLE_PROCESSED_INPUT)
        return True

    def on_break(self) -> None:
        """A Ctrl+Break is about to end the process: leave the terminal as the session found it."""
        steps = []
        if self._write is not None:
            steps.append(lambda: self._write(TERMINAL_RESET))
        if self._saved_mode is not None and self._handle is not None:
            steps.append(lambda: self._k32.SetConsoleMode(self._handle, self._saved_mode))
        for step in steps:
            try:
                step()
            except Exception:
                pass

    def restore(self) -> None:
        if not self.active or self._restored:
            return
        self._restored = True
        steps = []
        if self._handler is not None:
            steps.append(lambda: self._k32.SetConsoleCtrlHandler(self._handler, False))
        if self._saved_mode is not None and self._handle is not None:
            steps.append(lambda: self._k32.SetConsoleMode(self._handle, self._saved_mode))
        if self._signal is not None and self._saved_sigint is not None:
            steps.append(lambda: self._signal.signal(self._signal.SIGINT, self._saved_sigint))
        for step in steps:  # independent: one failing never skips the rest
            try:
                step()
            except Exception:
                pass


def install(*, kernel32: Any = None, platform: Optional[str] = None,
            signal_module: Any = None, write: Any = None) -> Guard:
    """Harden the console for the TUI's lifetime; see the module docstring.
    A no-op (inert Guard) off Windows. Never raises."""
    if (platform or sys.platform) != "win32":
        return Guard()
    guard = Guard()
    try:
        k32 = kernel32 if kernel32 is not None else _real_kernel32()
        handle = k32.GetStdHandle(STD_INPUT_HANDLE)
        guard = Guard(k32=k32, handle=handle, write=write if write is not None or kernel32 is not None
                      else _write_terminal)
        saved = guard._mode()
        guard._saved_mode = saved
        if saved is not None and saved & ENABLE_PROCESSED_INPUT:
            k32.SetConsoleMode(handle, saved & ~ENABLE_PROCESSED_INPUT)

        def _on_ctrl(ctrl_type: int) -> bool:
            if ctrl_type == CTRL_BREAK_EVENT:  # it still ends the process; the terminal is put back first
                guard.on_break()
                return False
            if ctrl_type != CTRL_C_EVENT:
                return False
            try:
                guard.ctrl_c_event()
            except Exception:
                pass
            return True  # handled, nobody else sees it: the process never ends by it

        guard._handler = _handler_type()(_on_ctrl)
        k32.SetConsoleCtrlHandler(guard._handler, True)
        if signal_module is None and kernel32 is None:
            import signal as signal_module  # real run only; a fake never touches process signals
        if signal_module is not None:
            guard._signal = signal_module
            guard._saved_sigint = signal_module.getsignal(signal_module.SIGINT)
            signal_module.signal(signal_module.SIGINT, signal_module.SIG_IGN)
        atexit.register(guard.restore)
        return guard
    except Exception:
        guard.restore()
        return Guard()
