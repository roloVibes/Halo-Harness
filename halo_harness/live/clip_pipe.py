"""halo_harness.live.clip_pipe -- the clip's Chrome speaks DevTools over two pipes, not a port (Halo 3.4.1.2, the
2026-11-12 review's SERVERS-5 / PACKS-8; live/clip_chrome.py).

`--remote-debugging-pipe` makes Chrome read commands from fd 3 and write answers to fd 4, each message a JSON text
ended by a NUL byte. `spawn(argv)` starts Chrome with `os.posix_spawn` (Linux, macOS): fd 3 and fd 4 are the child's
ends of two pipes, fd 0 / 1 / 2 are /dev/null, and nothing else of this process reaches it. No socket is opened, so
no other process on the machine can list or attach to the page while it holds a Studio token.

    proc, pipe = spawn(argv)     # proc: wait(timeout) / kill() / poll(); pipe: send(text) / recv() / close()
"""

from __future__ import annotations

import os
import select
import signal
import time

READ_TIMEOUT_S = 60.0


class Pipe:
    def __init__(self, w: int, r: int):
        self.w, self.r, self.buf = w, r, b""

    def send(self, text: str) -> None:
        data = text.encode("utf-8") + b"\0"
        while data:
            n = os.write(self.w, data)
            data = data[n:]

    def recv(self) -> str:
        deadline = time.time() + READ_TIMEOUT_S
        while b"\0" not in self.buf:
            left = deadline - time.time()
            if left <= 0 or not select.select([self.r], [], [], left)[0]:
                raise TimeoutError("Chrome said nothing on its DevTools pipe")
            chunk = os.read(self.r, 1 << 16)
            if not chunk:
                raise RuntimeError("Chrome closed its DevTools pipe")
            self.buf += chunk
        msg, self.buf = self.buf.split(b"\0", 1)
        return msg.decode("utf-8")

    def close(self) -> None:
        for fd in (self.w, self.r):
            try:
                os.close(fd)
            except OSError:
                pass


class Proc:
    """The few Popen methods clip_chrome.Chrome.close uses, for a pid posix_spawn made."""

    def __init__(self, pid: int):
        self.pid, self.returncode = pid, None

    def poll(self):
        if self.returncode is None:
            pid, status = os.waitpid(self.pid, os.WNOHANG)
            if pid:
                self.returncode = os.waitstatus_to_exitcode(status)
        return self.returncode

    def wait(self, timeout: float = 10):
        deadline = time.time() + timeout
        while self.poll() is None:
            if time.time() > deadline:
                raise TimeoutError(f"Chrome (pid {self.pid}) did not exit")
            time.sleep(0.05)
        return self.returncode

    def kill(self) -> None:
        try:
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
        except (OSError, ChildProcessError):
            pass


def _high(fd: int) -> int:
    """`fd` moved to 10 or above (close-on-exec), so no source of the dup2s below is fd 3 or 4 itself."""
    import fcntl
    try:
        return fcntl.fcntl(fd, fcntl.F_DUPFD_CLOEXEC, 10)
    finally:
        os.close(fd)


def spawn(argv: list) -> "tuple[Proc, Pipe]":
    """Chrome with its DevTools on pipes: fd 3 its commands, fd 4 its answers."""
    to_chrome_r, to_chrome_w = (_high(fd) for fd in os.pipe())
    from_chrome_r, from_chrome_w = (_high(fd) for fd in os.pipe())
    actions = [(os.POSIX_SPAWN_OPEN, 0, os.devnull, os.O_RDONLY, 0), (os.POSIX_SPAWN_OPEN, 1, os.devnull, os.O_WRONLY, 0),
               (os.POSIX_SPAWN_OPEN, 2, os.devnull, os.O_WRONLY, 0),
               (os.POSIX_SPAWN_DUP2, to_chrome_r, 3), (os.POSIX_SPAWN_DUP2, from_chrome_w, 4)]
    try:
        pid = os.posix_spawn(argv[0], argv, dict(os.environ), file_actions=actions)
    finally:
        os.close(to_chrome_r)
        os.close(from_chrome_w)
    return Proc(pid), Pipe(to_chrome_w, from_chrome_r)
