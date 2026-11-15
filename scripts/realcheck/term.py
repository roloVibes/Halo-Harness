"""scripts/realcheck/term.py -- a real terminal for one child, the way a person's terminal window holds it.

    t = Terminal(argv, env=env, cwd=cwd)     # a pty (Linux, macOS) or a pseudoconsole (Windows), 120 x 40
    t.text() / t.raw()                       # what it printed so far (the bytes, escapes included)
    t.ctrl_c()                               # the key a person presses: byte 0x03 typed into the terminal
    t.close_window()                         # the terminal goes away: the pty's master closes (SIGHUP), or the
                                             # pseudoconsole closes (CTRL_CLOSE_EVENT)
    t.hard_kill()                            # the top process ends at once (SIGKILL / TerminateProcess)
    t.poll() / t.wait(s) / t.pid

The child sees a terminal on stdin, stdout and stderr (isatty() is true), so `halo` and `halo init` take the path a
person's launch takes. Output is read on a thread the whole time (a full pipe would stall the child)."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time

ANSI = re.compile(r"\x1b(\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(\x07|\x1b\\)|[PX^_][^\x1b]*\x1b\\|[@-Z\\-_])")


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


class _Base:
    pid: int = 0

    def __init__(self) -> None:
        self._buf = bytearray()
        self._lock = threading.Lock()
        self.first_byte_at = 0.0
        self.started_at = time.monotonic()

    def _got(self, data: bytes) -> None:
        with self._lock:
            if not self._buf and data:
                self.first_byte_at = time.monotonic()
            self._buf.extend(data)
        if b"\x1b[6n" in data:  # a cursor-position query: a real terminal answers it, so this one does too
            self.write(b"\x1b[1;1R")

    def raw(self) -> bytes:
        with self._lock:
            return bytes(self._buf)

    def text(self) -> str:
        return self.raw().decode("utf-8", "replace")

    def plain(self) -> str:
        return strip_ansi(self.text())

    def wait_for(self, pred, timeout: float) -> bool:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if pred(self.plain()):
                return True
            if self.poll() is not None:
                time.sleep(0.2)
                return bool(pred(self.plain()))
            time.sleep(0.05)
        return bool(pred(self.plain()))

    def ctrl_c(self) -> None:
        self.write(b"\x03")

    def type(self, text: str) -> None:
        self.write(text.encode("utf-8"))


class PosixTerminal(_Base):
    def __init__(self, argv, *, env, cwd, cols: int = 120, rows: int = 40) -> None:
        super().__init__()
        import fcntl
        import struct
        import termios
        master, slave = os.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

        def own_session() -> None:  # a new session whose controlling terminal is this pty, as a terminal window gives
            os.setsid()
            fcntl.ioctl(0, termios.TIOCSCTTY, 0)

        self.proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, cwd=cwd,
                                     preexec_fn=own_session, close_fds=True)
        os.close(slave)
        self.pid, self._master = self.proc.pid, master
        self._closing = threading.Event()
        self._pump_thread = threading.Thread(target=self._pump, daemon=True)
        self._pump_thread.start()

    def _pump(self) -> None:
        """Read with select, never a blocking read: a read in flight keeps the master open after close()."""
        import select
        fd = self._master
        while not self._closing.is_set():
            try:
                ready, _, _ = select.select([fd], [], [], 0.1)
                if not ready:
                    continue
                data = os.read(fd, 65536)
            except (OSError, ValueError):
                return
            if not data:
                return
            self._got(data)

    def write(self, data: bytes) -> None:
        try:
            os.write(self._master, data)
        except OSError:
            pass

    def close_window(self) -> None:
        """The window goes: the master's last descriptor closes, so the kernel hangs the terminal up (SIGHUP to the
        session it leads)."""
        if self._master >= 0:
            self._closing.set()
            self._pump_thread.join(2)
            m, self._master = self._master, -1
            try:
                os.close(m)
            except OSError:
                pass

    def hard_kill(self) -> None:
        try:
            self.proc.kill()
        except OSError:
            pass

    def poll(self):
        return self.proc.poll()

    def wait(self, timeout: float):
        try:
            return self.proc.wait(timeout)
        except subprocess.TimeoutExpired:
            return None

    def cleanup(self) -> None:
        self.close_window()


def Terminal(argv, *, env, cwd, cols: int = 120, rows: int = 40):
    if sys.platform == "win32":
        from realcheck.conpty import ConPtyTerminal
        return ConPtyTerminal(argv, env=env, cwd=cwd, cols=cols, rows=rows)
    return PosixTerminal(argv, env=env, cwd=cwd, cols=cols, rows=rows)
