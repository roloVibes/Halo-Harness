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
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_browser_cdp import _Locked, _scratch, _tree_pids  # noqa: E402  (sets a scratch home first)
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

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
def test_a_quit_leaves_the_sessions_own_browser_to_its_own_close(ctx: Ctx):
    """A quit's ledger stop (children_stop.stop_for_quit) runs BEFORE the closing procedure; on Windows it is a hard end
    (taskkill, then the tree), which loses what the browser had not written yet: the kept profile's sign-in. So it never
    takes this process's own browser (Browser.close, registered with closing.on_close, ends it the polite way); a
    browser a gone session left behind is still stopped like any orphan."""
    from unittest import mock
    from halo_harness import children_stop as S
    me = os.getpid()
    rows = [{"pid": 101, "what": "browser", "owner_pid": me, "cmd": ["chrome"]},
            {"pid": 102, "what": "bg", "owner_pid": me, "cmd": ["halo"]},
            {"pid": 103, "what": "browser", "owner_pid": 999999, "cmd": ["chrome"]}]
    with mock.patch.object(S.C, "prune", lambda state_dir=None: rows), \
            mock.patch.object(S, "other_live_sessions", lambda: []), \
            mock.patch.object(S.C, "owner_alive", lambda e: e.get("owner_pid") == me):
        got = [e["pid"] for e in S.quit_targets()]
    ctx.check(f"the quit stops this session's other children and a gone session's browser, never its own browser, "
              f"got {got}", got == [102, 103])
    from halo_harness import headless
    stopped = []
    with mock.patch("halo_harness.children.prune", lambda state_dir=None: rows), \
            mock.patch.object(S, "stop_entry", lambda e, **k: stopped.append(e["pid"]) or {"what": e["what"],
                                                                                          "pid": e["pid"], "ok": True}):
        headless._stop_own_children_quietly()
    ctx.check(f"a `-p` run's own stop leaves its browser to Browser.close too, got {stopped}", stopped == [102])


@test
def test_every_orderly_way_out_ends_the_browser_first_and_within_3_s(ctx: Ctx):
    """W batch 3 entry 2: ONE function ends a session's browsers in order (browser_cdp.end_browsers: Browser.close asks,
    waits up to 3 s, then the hard stop by pid), and every orderly way out calls it BEFORE any other stop of the
    session's children: the terminal app's quit and a Studio session's end (Controller.quit) and the terminal app's
    force quit (Ctrl+C twice and Enter, Ctrl+Q). A `-p` run's is in its real test (tests.test_browser_tool_real)."""
    from types import SimpleNamespace
    from unittest import mock
    from halo_harness import browser_cdp as B
    from halo_harness import controller as Cm
    ctx.check("the bound is 3 s", getattr(B, "END_WAIT_S", None) == 3.0)
    order: list = []
    jobs = SimpleNamespace(kill_all=lambda: order.append("jobs"))
    sess = SimpleNamespace(_stopping=mock.MagicMock(), abort=mock.MagicMock(), job_registry=jobs,
                           _fire_session_end=lambda _w: None, close_runtimes=lambda: order.append("runtimes"))
    fake = SimpleNamespace(quit_called=False, session=sess, quit_stops_children=True, commands=mock.MagicMock(),
                           _worker=None, _stopped=mock.MagicMock(), state_dir=None, mcp_manager=None, exit_code=0,
                           _end_bang_work=lambda: order.append("bang"))  # 3.6.0.12: the quit ends `!` work too
    with mock.patch.object(B, "end_browsers", lambda *a, **k: order.append("browser"), create=True), \
            mock.patch.object(Cm, "_stop_children_for_quit", lambda _s: order.append("children") or ""), \
            mock.patch("halo_harness.closing.arm_close_deadline", lambda *a, **k: None):
        Cm.Controller.quit(fake)
    ctx.check(f"the quit (the terminal app's, a Studio session's end): the browser first, got {order}",
              order[:1] == ["browser"] and "jobs" in order and "children" in order and "bang" in order)
    from halo_harness.tui import app as A
    order.clear()
    me = SimpleNamespace(controller=SimpleNamespace(session=sess, state_dir=None, quit=lambda: 0, stopped_line=""),
                         _exit_message=lambda: None, call_from_thread=lambda *a, **k: None, exit=lambda **k: None,
                         _post_exit=lambda **k: None)  # 3.6.0.18 L: Ctrl+Q posts exit, never waits for the loop
    with mock.patch.object(B, "end_browsers", lambda *a, **k: order.append("browser"), create=True), \
            mock.patch("halo_harness.children_stop.stop_for_quit", lambda *a, **k: order.append("children") or ""), \
            mock.patch("threading.Timer", lambda *a, **k: SimpleNamespace(start=lambda: None, daemon=True)):
        A.BridgeApp._force_quit_worker(me)
    ctx.check(f"the force quit: the browser first, got {order}", order[:1] == ["browser"] and "children" in order)


@test
def test_the_browsers_end_keeps_to_the_quits_deadline(ctx: Ctx):
    """W batch 3 repair (the checker): a quit's way out shares one deadline (closing.QUIT_BUDGET_S); the browser's
    orderly end takes its share of it and leaves Controller.QUIT_RESERVE_S for the stops after, never all of it."""
    from types import SimpleNamespace
    from unittest import mock
    from halo_harness import browser_cdp as B
    from halo_harness import closing
    from halo_harness import controller as Cm
    got: list = []
    with mock.patch.object(B, "end_browsers", lambda limit=None: got.append(limit)), \
            mock.patch.object(closing, "time_left", lambda cap: min(cap, closing.QUIT_BUDGET_S)):
        Cm._end_browsers()
    ctx.check(f"an armed deadline: the browsers get it less the reserve, got {got}",
              got == [closing.QUIT_BUDGET_S - Cm.QUIT_RESERVE_S])
    got.clear()
    with mock.patch.object(B, "end_browsers", lambda limit=None: got.append(limit)):
        Cm._end_browsers()  # no deadline armed (a test, a Studio hosting a session): the browser's own bound
    ctx.check(f"no deadline: the browser's own bound, got {got}", got == [B.END_WAIT_S + 2.0])

    class Slow:  # a browser whose close never ends in time
        proc = SimpleNamespace(pid=0)

        def close(self):
            time.sleep(30)
    slow = Slow()
    with mock.patch.object(B, "_LIVE", [slow]):
        t = time.monotonic()
        B.end_browsers(0.2)
        took = time.monotonic() - t
    ctx.check(f"end_browsers returns at its limit, took {took:.1f} s", took < 2.0)


@test
def test_studio_stopping_waits_out_a_sessions_browser_close(ctx: Ctx):
    """W batch 3 repair (the checker): Studio stopping gives each session it started its `shutdown` and waits for it to
    leave before the hard end; that wait covers the session's browser close (END_WAIT_S), or a close of 2 to 3 s is cut
    by the hard end and the sign-in is lost on Windows. Counted on an injected clock."""
    from types import SimpleNamespace
    from unittest import mock
    from halo_harness import browser_cdp as B
    from halo_harness.studio import live_agents_api as L
    from halo_harness.studio import sessions_new_api as S
    clock = [0.0]
    proc = SimpleNamespace(pid=424242, poll=lambda: None)  # a session that never leaves by itself
    fake_time = SimpleNamespace(monotonic=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s))
    with mock.patch.object(S, "_procs", {424242: proc}), \
            mock.patch.object(S, "_rows", {424242: {"session_id": "s" * 12, "cwd": "."}}), \
            mock.patch.object(S, "time", fake_time), mock.patch.object(L, "forward", lambda *a, **k: None), \
            mock.patch.object(L, "caller", lambda: {}):
        rows = S.end_started()
    ctx.check(f"the session is named, got {rows}", len(rows) == 1)
    ctx.check(f"the wait covers the browser's close, waited {clock[0]:.1f} s", B.END_WAIT_S < clock[0] < B.END_WAIT_S + 2)


@test
def test_a_close_that_is_not_answered_ends_the_browser_hard_within_3_s(ctx: Ctx):
    """Browser.close asks, waits up to END_WAIT_S for the browser to be gone, and then stops it hard: never longer."""
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home = Path(_scratch("browser-closing-bound-"))
    with _Locked():
        b = B.Browser("clean", home=home)
        try:
            b.start()
            profile = b.profile
            b.pipe.call = lambda _m, _p, _s, timeout: time.sleep(min(timeout, 30)) or {}  # never answers its close
            t = time.monotonic()
            b.close()
            took = time.monotonic() - t
        finally:
            b.close()
    ok, left = _gone_within(profile, 0.5)
    ctx.check(f"the close returned within the bound, took {took:.1f} s", took < B.END_WAIT_S + 2.0)
    ctx.check(f"and nothing of the browser is left, left {left}", ok)
    _end_left(left)


@test
def test_a_hard_end_of_the_session_ends_its_browser_within_5_s(ctx: Ctx):
    from halo_harness import browser_cdp as B
    from halo_harness.browser_find import find_browser
    if find_browser() is None:
        ctx.check("a browser on this machine", False)
        return
    home = Path(_scratch("browser-closing-hard-"))
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
            ctx.check(f"and its own temp folder, got {info.get('tmp')!r}", bool(info.get("tmp"))
                      and os.path.isdir(info["tmp"]))
            b = B.Browser("clean", home=home)
            try:
                b.start()
                ctx.check("the next start removed the folder the hard end left", not os.path.isdir(info["profile"]))
                ctx.check("and the temp folder of the dead session (W batch 3 entry 1)",
                          bool(info.get("tmp")) and not os.path.isdir(info["tmp"]))
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
    home = Path(_scratch("browser-closing-close-"))
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
    home = Path(_scratch("browser-closing-ledger-"))
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


@test
def test_a_hard_kill_while_the_browser_waits_suspended_for_its_job_leaves_nothing(ctx: Ctx):
    """3.6.0.23 J P2 (Windows): Halo's browser starts suspended (browser_pipe_win.spawn) and runs only once it is in
    its Jobs. A hard kill of Halo before the move left it suspended in no Job of Halo's, for good. Now it is born in
    Halo's own Job, so it ends with Halo at every instant. The browser here is a stand-in (a Python that would sleep;
    held suspended, it never runs); no real browser starts."""
    if os.name != "nt":
        raise SkipTest("Windows only: the pipe by handles and the Job objects are Windows'")
    import shutil
    import tempfile
    from tests import test_kept_outlives_starter as K
    tmp = Path(tempfile.mkdtemp(prefix="fx-j-browser-"))
    start = '''from halo_harness import browser_pipe_win
browser_pipe_win.spawn(SLEEP, subprocess_safe.Popen)'''
    proc, left = K._moment_child(tmp, start), []
    try:
        K._killed_in_the_moment(ctx, proc, "the browser stand-in", left)
    finally:
        if proc.poll() is None:
            proc.kill()
        for child in left:
            K._end(*child)  # by pid and start time: a stand-in left suspended would stay for good
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
