"""tests.test_start_bytes -- 3.6.0.0 R12: a session started in Apple Terminal writes no BEL.

An Apple silicon Mac beeped when a session started in Apple Terminal. The bytes a real `halo` session writes to its
terminal at start, captured on a pty with Apple Terminal's environment (`TERM_PROGRAM=Apple_Terminal`,
`TERM=xterm-256color`, no `COLORTERM`), held `ESC ] 22 ; default BEL` (Textual's pointer shape: an OSC Apple
Terminal does not know, so its closing BEL rings), `ESC [ ? 2048 $ p` (a DECRQM query Apple Terminal mishandles)
and Halo's own BEL-closed title. Here the same start on a pty: under that profile no BEL byte at all and none of
those sequences; under an ordinary terminal profile the title is still written (so the capture is real).

POSIX only: a pty is how a terminal sees a process; Windows has no pty here and no Apple Terminal.
"""
from __future__ import annotations

import os
import select
import signal
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
ALT_SCREEN = b"\x1b[?1049h"


def _start_bytes(term_program: str, *, settle_s: float = 3.0, cap_s: float = 60.0) -> bytes:
    """Every byte `halo` writes to its pty from launch until its first screen has settled, then the process (ours)
    is ended. A scratch home, a mock model on a closed port, no network, no Ollama, no browser."""
    try:
        import pty
    except ImportError:
        raise SkipTest("no pty module here")
    root = Path(tempfile.mkdtemp(prefix="start-bytes-"))
    (root / "home").mkdir()
    (root / "proj").mkdir()
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root / "home"), "LANG": "en_US.UTF-8",
           "TMPDIR": os.environ.get("TMPDIR", "/tmp"), "TERM": "xterm-256color", "PYTHONPATH": str(REPO),
           "HALO_NO_BROWSER": "1", "OLLAMA_HOST": "http://127.0.0.1:9", "BRIDGE_TEST_NO_BACKGROUND_NET": "1",
           "OPENROUTER_API_KEY": "sk-or-test", "BRIDGE_OPENROUTER_BASE_URL": "http://127.0.0.1:9",
           "BRIDGE_TEST_HOME": str(root / "home")}
    if term_program:
        env["TERM_PROGRAM"] = term_program
    pid, fd = pty.fork()
    if pid == 0:  # the child: the session, on the pty
        os.chdir(str(root / "proj"))
        os.execve(sys.executable, [sys.executable, "-m", "halo_harness", "--model", "or:mock/start-bytes"], env)
    buf = bytearray()
    t0 = last = time.monotonic()
    try:
        while time.monotonic() - t0 < cap_s:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r:
                try:
                    data = os.read(fd, 65536)
                except OSError:
                    break
                if not data:
                    break
                buf += data
                last = time.monotonic()
            elif ALT_SCREEN in buf and len(buf) > 2000 and time.monotonic() - last > settle_s:
                break
            if os.waitpid(pid, os.WNOHANG)[0]:
                pid = 0
                break
    finally:
        if pid:
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.kill(pid, sig)
                except OSError:
                    break
                for _ in range(20):
                    if os.waitpid(pid, os.WNOHANG)[0]:
                        pid = 0
                        break
                    time.sleep(0.1)
                if not pid:
                    break
        os.close(fd)
    return bytes(buf)


@test
def test_a_session_in_apple_terminal_writes_no_bel_at_start(ctx: Ctx):
    if os.name == "nt":
        raise SkipTest("no pty on Windows (and no Apple Terminal)")
    out = _start_bytes("Apple_Terminal")
    ctx.check(f"the session really drew its screen ({len(out)} bytes)", ALT_SCREEN in out and len(out) > 2000)
    i = out.find(b"\x07")
    ctx.check(f"no BEL byte at all, got one at {i}: {out[max(0, i - 40):i + 1]!r}", i < 0)
    ctx.check("no OSC 22 pointer shape (Apple Terminal has none)", b"\x1b]22;" not in out)
    ctx.check("no DECRQM `$p` query (Apple Terminal prints a 'p')", b"$p" not in out)
    ctx.check("no window title (left to Apple Terminal)", b"\x1b]2;" not in out and b"\x1b]0;" not in out)


@test
def test_any_other_terminal_still_gets_its_title(ctx: Ctx):
    if os.name == "nt":
        raise SkipTest("no pty on Windows")
    out = _start_bytes("")
    ctx.check(f"the session really drew its screen ({len(out)} bytes)", ALT_SCREEN in out and len(out) > 2000)
    ctx.check("Halo's own title is on the wire, so the capture sees what Halo writes", b"\x1b]2;halo\x07" in out)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
