"""tests.test_browser_closing -- everything Halo starts ends with it, Halo's own browser too (3.6.0.6 W entry 2): a
stand-in session (tests/helpers/browser_standin.py) that holds a real browser is ended HARD (SIGKILL; on Windows
TerminateProcess): within 5 s no process carries the browser's profile, and the clean profile folder it left is
removed by the next start; the closing procedure (closing.close, every way out) ends it too, and the ledger lists it
as `browser` while it runs. Needs a Chromium-family browser installed (every CI leg has Chrome).
Run: python -m tests.test_browser_closing
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("BRIDGE_TEST_HOME", tempfile.mkdtemp(prefix="browser-closing-home-"))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_browser_cdp import _Locked, _tree_pids  # noqa: E402

test, TESTS = new_registry()
GONE_S = 5.0


def _standin(home: Path, profile: str, *extra: str):
    env = dict(os.environ, BRIDGE_TEST_HOME=str(home), BRIDGE_STATE_DIR=str(home / "state"), PYTHONPATH=str(ROOT))
    p = subprocess.Popen([sys.executable, "-m", "tests.helpers.browser_standin", str(home), profile, *extra],
                         cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    line = p.stdout.readline()
    try:
        return p, json.loads(line)
    except ValueError:
        p.kill()
        out, err = p.communicate(timeout=30)
        raise AssertionError(f"the stand-in did not start its browser: {line!r} {err[-600:]!r}")


def _gone_within(profile: str, seconds: float) -> "tuple[bool, list]":
    end = time.monotonic() + seconds
    left = _tree_pids(profile)
    while left and time.monotonic() < end:
        time.sleep(0.2)
        left = _tree_pids(profile)
    return not left, left


def _end_left(pids: list) -> None:
    from tests.helpers.leftovers import scan, end_one
    table = scan(lambda _pid, _start: True)
    for pid in pids:
        if pid in table:
            end_one(table[pid])


@test
def test_a_hard_end_of_the_session_ends_its_browser_within_5_s(ctx: Ctx):
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home = Path(tempfile.mkdtemp(prefix="browser-closing-hard-"))
    with _Locked():
        p, info = _standin(home, "clean")
        left = []
        try:
            ctx.check("the browser runs while the session does", bool(_tree_pids(info["profile"])))
            p.kill()  # SIGKILL on POSIX, TerminateProcess on Windows: no Python runs in the session
            p.wait(timeout=30)
            ok, left = _gone_within(info["profile"], GONE_S)
            ctx.check(f"every browser process gone within {GONE_S:.0f} s, left {left}", ok)
            ctx.check("the hard end left its clean profile folder", os.path.isdir(info["profile"]))
            b = B.Browser("clean", home=home)
            try:
                b.start()
                ctx.check("the next start removed the folder the hard end left", not os.path.isdir(info["profile"]))
            finally:
                b.close()
        finally:
            if p.poll() is None:
                p.kill()
            p.communicate(timeout=30)
            _end_left(left)


@test
def test_the_closing_procedure_ends_the_browser_and_the_ledger_named_it(ctx: Ctx):
    from halo_harness import children
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home = Path(tempfile.mkdtemp(prefix="browser-closing-close-"))
    with _Locked():
        p, info = _standin(home, "kept", "close")
        try:
            out, err = p.communicate(timeout=60)
            ctx.check(f"closing.close() ran, got {out!r} {err[-300:]!r}", "closed" in out)
            ok, left = _gone_within(info["profile"], GONE_S)
            ctx.check(f"no browser process left, left {left}", ok)
            ctx.check("the kept profile stays", os.path.isdir(info["profile"]))
            rows = [r for r in children.load(state_dir=home / "state") if r.get("what") == "browser"]
            ctx.check(f"the ledger row went with it, got {rows}", not rows)
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=30)


@test
def test_the_ledger_lists_a_running_browser_as_browser(ctx: Ctx):
    from halo_harness import children
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home = Path(tempfile.mkdtemp(prefix="browser-closing-ledger-"))
    with _Locked():
        p, info = _standin(home, "clean")
        try:
            rows = [r for r in children.load(state_dir=home / "state") if r.get("what") == "browser"]
            ctx.check(f"one `browser` row for its pid, owned by the session, got {rows}",
                      len(rows) == 1 and rows[0]["pid"] == info["browser"] and rows[0]["owner_pid"] == info["pid"])
            ctx.check("`halo ps` calls it a browser", children.label("browser") == "browser")
        finally:
            p.kill()
            p.communicate(timeout=30)
            ok, left = _gone_within(info["profile"], GONE_S)
            _end_left(left)
            ctx.check("gone after", ok)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
