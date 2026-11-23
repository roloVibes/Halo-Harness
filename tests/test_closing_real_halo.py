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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
