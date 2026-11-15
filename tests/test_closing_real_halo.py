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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
