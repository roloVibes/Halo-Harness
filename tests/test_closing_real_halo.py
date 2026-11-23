"""tests.test_closing_real_halo -- the closing procedure of the REAL `halo` (3.6.0.0 R10), not a stand-in.

tests/test_closing.py ends owners that install the closing procedure themselves (tests/helpers/closing_owner.py, a
`python -c` that calls closing.install()): with `halo` itself no longer installing it (cli.main skipping
closing.install()) 23 of its 24 tests still passed. Here the real `halo init` (`python -m halo_harness init`, the way
the console script runs cli.main) starts in a terminal of its own (a pty / a pseudoconsole: scripts/realcheck's
Terminal) in a scratch home, prints its Studio's address, and is ended the ways a person ends it: Ctrl+C (Ctrl+Break
where a launcher switched Ctrl+C off, and said), its terminal closed, a hard kill of the top process. The Studio it
started (its pid and start time from studio.json) must be gone within BOUND_S, and nothing started under the scratch
home may be left. Nothing here talks to a network: the provider and the browser are scripts/realcheck's stand-ins."""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from realcheck import core, procs  # noqa: E402
from realcheck.steps_close import HOW, _end, _studio_pid  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
BOUND_S = 10.0  # the Studio a launch started is gone this long after the launch ended


def _same(pid: int, started: float) -> bool:
    """`pid` still names the process that started at `started` (never another program the pid was given to)."""
    if not pid or not procs.alive(pid):
        return False
    now = procs.started_at(pid)
    return not started or not now or abs(now - started) <= 2


def _close_init(c: "core.Ctx", how: str) -> dict:
    h = c.home("init")
    env = c.env(h, HALO_NO_UPDATER="1", BRIDGE_TEST_NO_BACKGROUND_NET="1")
    t = c.terminal(h, "init", env=env)
    row: dict = {"how": how}
    try:
        url, at, _seen = core.wait_address(c, h, t, 60)
        row["address_s"] = round(at, 1)
        if not url:
            row["not_up"] = core.excerpt(t.plain(), 300) or f"exit {t.poll()}"
            return row
        pid = _studio_pid(h)
        started = procs.started_at(pid) if pid else 0.0
        row.update(studio=pid, studio_alive=_same(pid, started), init_alive=t.poll() is None)
        row["keys"] = _end(c, t, how, full_screen=False)
        end = time.monotonic() + BOUND_S
        while _same(pid, started) and time.monotonic() < end:
            time.sleep(0.2)
        row["studio_alive_after"] = _same(pid, started)
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 5.0)]
        return row
    finally:
        t.cleanup()
        c.end_leftovers(h)


def _check(ctx: Ctx, how: str) -> None:
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-init-")))
    try:
        row = _close_init(c, how)
    finally:
        c.close()
    ctx.check(f"`halo init` printed its Studio's address ({row.get('not_up', '')!r})", "not_up" not in row)
    ctx.check(f"before it was ended, `halo init` and the Studio it started both ran (not a vacuous check), got {row}",
              row["init_alive"] and row["studio"] and row["studio_alive"])
    ctx.check(f"{row['keys']}: its Studio (pid {row['studio']}) gone within {BOUND_S:.0f} s, got {row}",
              not row["studio_alive_after"])
    ctx.check(f"{row['keys']}: nothing started under the scratch home left 5 s later, got {row['left']}", not row["left"])


@test
def test_a_real_halo_init_ended_by_ctrl_c_takes_its_studio_with_it(ctx: Ctx):
    _check(ctx, HOW[0])


@test
def test_a_real_halo_init_whose_terminal_closes_takes_its_studio_with_it(ctx: Ctx):
    _check(ctx, HOW[1])


@test
def test_a_real_halo_init_killed_hard_takes_its_studio_with_it(ctx: Ctx):
    _check(ctx, HOW[2])


GONE_S = 5.0  # 3.6.0.17 Z1: a closed session is gone this long after its last key, its git with it


def _session_while_the_check_hangs(c: "core.Ctx") -> dict:
    """A real terminal session (bare `halo`) in a scratch home with no update cache: its update check at the start
    runs the stand-in `git` (tests/helpers/hanging_git.py: a hanging network), which is still waiting when the session
    is ended with Ctrl+C (its "Quit Halo?" answered with Enter, as a person does)."""
    import os
    from realcheck import screen
    from realcheck.steps_close import _noter
    from tests.helpers import hanging_git
    h = c.home("session")
    folder = hanging_git.make(h.dir / "git-standin")
    trace = h.dir / "close-trace.txt"
    # Never the real network: git is a stand-in, and every HTTP(S) request (the check's fallback to the API, and
    # anything else the session asks) goes to a proxy on a dead loopback port and fails at once.
    dead = "http://127.0.0.1:9"
    proxies = {k: dead for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")}
    env = c.env(h, PATH=f"{folder}{os.pathsep}{os.environ.get('PATH', '')}", HALO_NO_UPDATER="1",
                BRIDGE_TEST_NO_BACKGROUND_NET=None, HALO_OFFLINE=None, HALO_CLOSE_TRACE=str(trace),
                NO_PROXY=None, no_proxy=None, **proxies)
    t = c.terminal(h, env=env)
    row: dict = {}
    rows: list = []
    first = None
    try:
        end = time.monotonic() + 90
        while time.monotonic() < end and t.poll() is None:
            rows = hanging_git.seen(folder)
            if rows and first is None:
                first = time.monotonic()
            if rows and screen.READY.search(t.plain()):
                break
            time.sleep(0.2)
        row["standins"] = rows
        row["standins_alive"] = hanging_git.alive(rows)
        if not (rows and screen.READY.search(t.plain())):
            row["not_up"] = core.excerpt(t.plain(), 300) or f"exit {t.poll()}"
            return row
        time.sleep(1.0)  # keys typed the moment the status line shows may not be taken (the realcheck re-presses then)
        # the close must land DURING the hang: git and its helper still alive as the keys go (else nothing is proved)
        row["standins_alive_at_close"] = hanging_git.alive(rows)
        row["hung_s_at_close"] = round(time.monotonic() - (first or time.monotonic()), 1)
        row["keys"] = _end(c, t, HOW[0], full_screen=True, note=_noter(trace))
        end = time.monotonic() + GONE_S
        while t.poll() is None and time.monotonic() < end:
            time.sleep(0.1)
        row["halo_alive_after"] = t.poll() is None
        row["standins_alive_after"] = hanging_git.wait_gone(rows, max(0.0, end - time.monotonic()))
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 0.5)]
        return row
    finally:
        hanging_git.end(rows or hanging_git.seen(folder))
        t.cleanup()
        c.end_leftovers(h)


@test
def test_z1_a_session_closed_while_its_update_check_hangs_is_gone_with_its_git(ctx: Ctx):
    """3.6.0.17 Z1 (a): the closing rule while the network hangs: the Halo process gone within GONE_S of the Ctrl+C,
    and neither git nor its helper alive then (by pid and start time)."""
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-z1-")))
    try:
        row = _session_while_the_check_hangs(c)
    finally:
        c.close()
    ctx.check(f"the session came up and its update check's git and helper ran (not a vacuous check), got {row}",
              "not_up" not in row and len(row["standins_alive"]) == 2)
    ctx.check(f"the close landed while the check's git and helper still hung (not a vacuous check), got {row}",
              len(row.get("standins_alive_at_close") or []) == 2)
    ctx.check(f"{row.get('keys')}: the Halo process gone within {GONE_S:.0f} s, got {row}", not row["halo_alive_after"])
    ctx.check(f"{row.get('keys')}: no stand-in git left {GONE_S:.0f} s after the close, got {row}",
              not row["standins_alive_after"])
    ctx.check(f"{row.get('keys')}: nothing started under the scratch home left, got {row['left']}", not row["left"])


class _Silent:
    """3.6.0.17 Z2: a listener of this test's own on a loopback port that accepts and never answers -- a network read
    that hangs (a dead port is not enough: it refuses at once). `conns` are the connections it holds; close() ends
    them all (a test's `finally`)."""

    def __init__(self) -> None:
        import socket
        import threading
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(16)
        self.sock.settimeout(0.2)
        self.port = self.sock.getsockname()[1]
        self.conns: list = []
        self.first: "float | None" = None
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._accept, name="z2-silent", daemon=True)
        self._th.start()

    def _accept(self) -> None:
        import socket
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            self.first = self.first or time.monotonic()
            self.conns.append(conn)

    def close(self) -> None:
        self._stop.set()
        self._th.join(2)
        for s in self.conns + [self.sock]:
            try:
                s.close()
            except OSError:
                pass


_LAST_LINES = 6


def _last_lines(text: str) -> list:
    """The last non-empty lines a terminal shows (what a person reads once the session is gone)."""
    return [ln.rstrip() for ln in text.splitlines() if ln.strip()][-_LAST_LINES:]


def _z2_env(c: "core.Ctx", h, folder: Path, listener: "_Silent", trace: Path) -> dict:
    """A scratch home's session whose OpenRouter catalog and balance refreshes at launch read from `listener` (they
    hang), whose git answers at once (tests/helpers/hanging_git.py, hang=False) and whose every other HTTP(S) request
    goes to a proxy on a dead loopback port and fails at once: never the real network."""
    import os
    dead = "http://127.0.0.1:9"
    proxies = {k: dead for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy")}
    base = f"http://127.0.0.1:{listener.port}/api/v1"
    return c.env(h, PATH=f"{folder}{os.pathsep}{os.environ.get('PATH', '')}", HALO_NO_UPDATER="1",
                 BRIDGE_TEST_NO_BACKGROUND_NET=None, HALO_OFFLINE=None, HALO_CLOSE_TRACE=str(trace),
                 NO_PROXY=None, no_proxy=None, OPENROUTER_BASE_URL=base, BRIDGE_OPENROUTER_BASE_URL=base, **proxies)


def _quit_while_a_read_hangs(c: "core.Ctx", how: str) -> dict:
    """A real terminal session (bare `halo`) in a scratch home, ONE of its launch workers (the OpenRouter catalog
    refresh: a 30 s read) stuck on `_Silent`; the session is quit the way a person does (`how`: Ctrl+C then Enter on
    "Quit Halo?", or /quit). The Halo process must be gone within GONE_S, with the normal quit's code."""
    from realcheck import screen
    from realcheck.steps_close import _noter
    from tests.helpers import hanging_git
    h = c.home("z2")
    folder = hanging_git.make(h.dir / "git-standin", hang=False)
    trace = h.dir / "close-trace.txt"
    listener = _Silent()
    row: dict = {"how": how}
    t = None
    try:
        t = c.terminal(h, env=_z2_env(c, h, folder, listener, trace))
        end = time.monotonic() + 90
        while time.monotonic() < end and t.poll() is None:
            if listener.conns and screen.READY.search(t.plain()):
                break
            time.sleep(0.2)
        row["held"] = len(listener.conns)
        if not (listener.conns and screen.READY.search(t.plain())):
            row["not_up"] = core.excerpt(t.plain(), 300) or f"exit {t.poll()}"
            return row
        time.sleep(1.0)  # keys typed the moment the status line shows may not be taken
        row["held_s_at_quit"] = round(time.monotonic() - (listener.first or time.monotonic()), 1)
        if how == "/quit":
            t.type("/quit")
            time.sleep(0.3)
            t.write(b"\r")
            row["keys"] = "/quit Enter"
        else:
            row["keys"] = screen.quit_with_ctrl_c(t, wait=0.5, note=_noter(trace))
        end = time.monotonic() + GONE_S
        while t.poll() is None and time.monotonic() < end:
            time.sleep(0.1)
        row["halo_alive_after"] = t.poll() is None
        row["code"] = t.poll()
        row["last_lines"] = _last_lines(t.plain())
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 0.5)]
        return row
    finally:
        if t is not None:
            t.cleanup()
        listener.close()
        c.end_leftovers(h)


def _check_z2(ctx: Ctx, how: str) -> None:
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-z2-")))
    try:
        row = _quit_while_a_read_hangs(c, how)
    finally:
        c.close()
    ctx.check(f"the session came up and a launch worker's read hung on the test's listener (not a vacuous check), "
              f"got {row}", "not_up" not in row and row["held"] >= 1)
    ctx.check(f"{row.get('keys')}: the Halo process gone within {GONE_S:.0f} s of the quit, got {row}",
              not row["halo_alive_after"])
    ctx.check(f"{row.get('keys')}: it left with the normal quit's code 0, got {row.get('code')}", row.get("code") == 0)
    ctx.check(f"{row.get('keys')}: the terminal shows no traceback on the way out, got {row.get('last_lines')}",
              not any("Traceback" in ln for ln in row.get("last_lines") or []))
    ctx.check(f"{row.get('keys')}: nothing started under the scratch home left, got {row['left']}", not row["left"])


@test
def test_z2_a_session_quit_with_ctrl_c_while_a_launch_read_hangs_is_gone_within_the_bound(ctx: Ctx):
    """3.6.0.17 Z2-1: the terminal app's normal quit has the bound the other ways out have (closing.hard_exit): a
    pool thread in a hanging network read no longer keeps the quit Halo alive."""
    _check_z2(ctx, "Ctrl+C")


@test
def test_z2_a_session_quit_with_slash_quit_while_a_launch_read_hangs_is_gone_within_the_bound(ctx: Ctx):
    _check_z2(ctx, "/quit")


# The restart exit (/update's Enter) needs an update on offer and then hands over to the updater, so a real session
# cannot be driven to it here. This drives the same terminal app (`run_tui`, the demo controller) in a terminal of its
# own, with the real closing procedure installed as cli.main installs it, a thread worker of the app stuck on the
# test's listener, and then the very function /update's dialog calls with Enter (slash._on_update_dialog_result).
_RESTART = r'''
import socket, sys, threading
from halo_harness import closing
closing.install()  # what cli.main does first in the real process
from halo_harness import cli
from halo_harness.tui import app as A, slash
from halo_harness.tui.launch import run_tui
port = int(sys.argv[1])
_mount = A.BridgeApp.on_mount


async def on_mount(self):
    await _mount(self)

    def held():  # a launch worker in a network read that never answers
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        s.settimeout(120)
        self.call_from_thread(slash._on_update_dialog_result, self, "update")
        try:
            s.recv(1)
        except OSError:
            pass
    self.run_worker(held, thread=True, name="z2-held", group="z2-held")


A.BridgeApp.on_mount = on_mount
sys.exit(run_tui(cli._build_parser().parse_intermixed_args(["--demo"])))
'''


@test
def test_z2_the_restart_exit_keeps_its_code_through_the_bound(ctx: Ctx):
    """3.6.0.17 Z2-1: /update's restart exit (update.RESTART_EXIT_CODE) passes the same bound and keeps its code."""
    from realcheck.term import Terminal
    from halo_harness import closing
    from halo_harness.update import RESTART_EXIT_CODE
    # its controller.quit is still ahead when the app ends (tui/launch.py runs it): its budget is part of the bound
    bound = GONE_S + closing.QUIT_BUDGET_S
    c = core.Ctx(REPO, Path(tempfile.mkdtemp(prefix="rc-close-z2r-")))
    listener = _Silent()
    row: dict = {}
    t = None
    try:
        h = c.home("z2r")
        script = h.dir / "z2_restart.py"
        script.write_text(_RESTART, encoding="utf-8")
        env = c.env(h, HALO_NO_UPDATER="1", BRIDGE_TEST_NO_BACKGROUND_NET="1")
        t = Terminal([sys.executable, str(script), str(listener.port)], env=env, cwd=str(h.proj))
        c._mark(h, t.pid)
        c.terms.append(t)
        end = time.monotonic() + 90
        while time.monotonic() < end and t.poll() is None and not listener.conns:
            time.sleep(0.1)
        row["held"] = len(listener.conns)
        start = listener.first or time.monotonic()
        end = start + bound
        while t.poll() is None and time.monotonic() < end:
            time.sleep(0.1)
        row["alive_after"] = t.poll() is None
        row["code"] = t.poll()
        row["last_lines"] = _last_lines(t.plain())
        row["left"] = [f"{p.short(110)} [{p.why}]" for p in c.left_after(h, 0.5)]
    finally:
        if t is not None:
            t.cleanup()
        listener.close()
        c.end_leftovers()
        c.close()
    ctx.check(f"the app's worker read hung on the test's listener (not a vacuous check), got {row}", row["held"] >= 1)
    ctx.check(f"the process gone within {bound:.0f} s of the restart exit, got {row}", not row["alive_after"])
    ctx.check(f"it left with the restart exit's code {RESTART_EXIT_CODE}, got {row.get('code')}",
              row.get("code") == RESTART_EXIT_CODE)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
