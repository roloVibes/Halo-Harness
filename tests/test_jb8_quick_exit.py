"""tests.test_jb8_quick_exit -- the way out is bounded by one deadline and the Studio address waits for nothing it
does not need (Halo 3.6.0.0, fix package "jb8").

1. A quit stops the session's background Bash jobs at its first moment, before it waits for a turn still running:
   a turn that did not read the abort held the job's shell and its `sleep` (and Halo itself) for the worker join's
   5 s. The CI runner's realcheck row "session, background Bash job / Ctrl+C" found Halo, bash.exe and sleep.exe
   alive 5 s after the quit, all gone by 30 s.
2. The whole close shares one deadline (closing.QUIT_BUDGET_S from the quit's start): the worker join, the quit's
   stop of the session's children (all at once, never one after another) and the closing procedure's waits.
3. Windows: in a Job object that forbids breakaway (a CI runner's, another Halo's strict Job) the browser starts
   from outside every Job through closing.start_outside_job (a PowerShell start: 0.6-0.9 s on a fast PC, about 2 s
   on a CI runner), and `halo init` printed the Studio address only after it. open_url now hands that start to a
   thread and returns at once; the closing procedure waits for it within the deadline.
Every process a test starts uses a scratch home and is ended by pid and start time; nothing is killed by name.
Run: python -m tests.test_jb8_quick_exit
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
WIN = os.name == "nt"


def _scratch():
    home = Path(tempfile.mkdtemp(prefix="halo-jb8-"))
    env = mock.patch.dict(os.environ, {"BRIDGE_TEST_HOME": str(home), "OLLAMA_HOST": "http://127.0.0.1:9",
                                       "HALO_NO_UPDATER": "1"})
    return home, env


class _StuckTurnSession:
    """A session whose worker is inside a turn that does not read the abort (a provider call on a slow machine, a
    tool): `run` returns only after `hold_s`."""

    def __init__(self, registry, hold_s: float) -> None:
        self._stopping, self.abort = threading.Event(), threading.Event()
        self.job_registry, self.hold_s = registry, hold_s
        self.interactive, self.busy, self.turn_count = False, True, 1

    def run(self, commands, put, mcp_status_fn=None) -> int:
        time.sleep(self.hold_s)
        return 0

    def _fire_session_end(self, why: str) -> None:
        pass

    def close_runtimes(self) -> None:
        pass


@test
def test_a_quit_ends_a_background_job_at_once_and_returns_within_the_deadline_while_a_turn_holds(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.children import same_process
    from halo_harness.config.paths import git_bash
    from halo_harness.controller import Controller
    from tests.test_closing import _end_tree_we_started
    from tests.test_lifecycle_fx2_batch01 import _sleeping_job
    shell = git_bash()
    if shell is None:
        raise SkipTest("no bash here")
    home, env = _scratch()
    procs = []
    try:
        with env, mock.patch.dict(closing._STATE, {"installed": True, "deadline": None}):
            reg, rec, spid, sstart = _sleeping_job(home, shell)
            procs = [(spid, sstart)]
            session = _StuckTurnSession(reg, hold_s=8.0)
            c = Controller(session=session, cwd=home, state_dir=home / ".halo").start()
            done = {}
            t0 = time.monotonic()
            th = threading.Thread(target=lambda: done.setdefault("code", c.quit()), daemon=True)
            th.start()
            gone_at = None
            while time.monotonic() - t0 < 8.0:
                if gone_at is None and not same_process(spid, sstart):
                    gone_at = time.monotonic() - t0
                if gone_at is not None and not th.is_alive():
                    break
                time.sleep(0.05)
            th.join(10)
            took = time.monotonic() - t0
            ctx.check(f"the background job's sleep (pid {spid}) ended at the quit's start, not after the worker "
                      f"join: gone after {gone_at if gone_at is None else round(gone_at, 2)} s", gone_at is not None
                      and gone_at < 1.5)
            budget = getattr(closing, "QUIT_BUDGET_S", 4.0)
            ctx.check(f"quit() returned within the deadline ({budget:.0f} s) with the turn still running: took "
                      f"{took:.2f} s", "code" in done and took < budget)
    finally:
        for pid, start in procs:
            _end_tree_we_started(pid, start)
        shutil.rmtree(home, ignore_errors=True)


@test
def test_a_quit_stops_its_children_together_never_one_after_another(ctx: Ctx):
    """Three children whose stop takes 2 s each (a polite stop waited out): the quit's stop takes about 2 s, not 6."""
    from halo_harness import children_stop
    home, env = _scratch()
    rows = [{"pid": 4_000_000 + i, "what": "schedule", "cmd": ["sleeper"]} for i in range(3)]
    asked = []

    def slow_stop(entry, *, state_dir=None, timeout=5.0):
        asked.append(timeout)
        time.sleep(2.0)
        return {"what": entry["what"], "pid": entry["pid"], "ok": True, "cmd": entry["cmd"]}

    try:
        with env, mock.patch.object(children_stop, "quit_targets", lambda state_dir=None: list(rows)), \
                mock.patch.object(children_stop, "stop_entry", slow_stop):
            t0 = time.monotonic()
            line = children_stop.stop_for_quit(home / ".halo")
            took = time.monotonic() - t0
        ctx.check(f"three slow stops ran together: {took:.2f} s", len(asked) == 3 and took < 3.5)
        ctx.check(f"the quit still names what it stopped, got {line!r}", "stopped" in line)
    finally:
        shutil.rmtree(home, ignore_errors=True)


@test
def test_the_closing_procedure_waits_no_longer_than_what_is_left_of_the_deadline(ctx: Ctx):
    """A quit began 1.5 s ago: the closing procedure's polite and hard waits together fit in what is left."""
    from halo_harness import closing
    seen = {}

    def record(entries, *, state_dir=None, polite_s=0.0, hard_s=0.0):
        seen.update(polite_s=polite_s, hard_s=hard_s)
        return []

    pid, start = closing.me()
    row = {"pid": 4_000_123, "what": "schedule", "owner_pid": pid, "owner_start": start}
    with mock.patch.dict(closing._STATE, {"installed": True, "closed": False, "deadline": None, "callbacks": [],
                                          "spawned": False, "reaper": None}), \
            mock.patch.object(closing, "_entries", lambda state_dir=None: [row]), \
            mock.patch.object(closing, "stop_entries", record):
        closing.arm_close_deadline()
        time.sleep(1.5)
        closing.close(say=lambda _l: None)
    total = seen.get("polite_s", 99) + seen.get("hard_s", 99)
    ctx.check(f"polite + hard waits fit the {closing.QUIT_BUDGET_S:.0f} s deadline less the 1.5 s gone: {seen}",
              total <= closing.QUIT_BUDGET_S - 1.4 and seen.get("hard_s", 0) > 0)


@test
def test_unarmed_waits_keep_their_own_bounds(ctx: Ctx):
    """A process that is not on its way out (a test, Studio quitting a session it hosts) keeps each wait's own bound."""
    from halo_harness import closing
    with mock.patch.dict(closing._STATE, {"installed": False, "deadline": None}):
        closing.arm_close_deadline()
        ctx.check("not armed outside a real halo", closing._STATE.get("deadline") is None)
        ctx.check("a wait keeps its own bound", closing.time_left(5.0) == 5.0)


class _SlowPopen:
    """Stands for subprocess_safe.Popen of a browser that must start from outside every Job (start_outside_job's
    PowerShell start: about 2 s on a CI runner)."""
    seen: list = []

    def __init__(self, args, **kw):
        time.sleep(1.5)
        _SlowPopen.seen.append(args)
        self.pid = 0


@test
def test_windows_a_browser_an_outer_job_holds_never_holds_up_the_caller(ctx: Ctx):
    if not WIN:
        ctx.check("POSIX has no Job objects: open_url asks webbrowser", True)
        return
    from halo_harness import closing
    from halo_harness import subprocess_safe
    url = "http://127.0.0.1:1/?mode=setup#t=x"
    prog = str(Path(tempfile.gettempdir()) / "jb8 browser" / "b.exe")
    _SlowPopen.seen = []
    with mock.patch.object(closing, "_in_a_job", lambda: True), \
            mock.patch.object(closing, "breakaway_frees", lambda: False), \
            mock.patch.object(subprocess_safe, "Popen", _SlowPopen), \
            mock.patch.dict(os.environ, {"BROWSER": prog}), \
            mock.patch.dict(closing._STATE, {"closed": False, "owner_gone": False, "hard_exit": None}):
        t0 = time.monotonic()
        ok = closing.open_url(url)
        took = time.monotonic() - t0
        closing.wait_for_browsers(10.0)
    ctx.check(f"open_url returned at once ({took:.2f} s), the start goes on beside the caller", ok and took < 0.5)
    ctx.check(f"the browser named by BROWSER got the URL, got {_SlowPopen.seen}", _SlowPopen.seen == [[prog, url]])


@test
def test_windows_a_browser_breakaway_lets_go_starts_before_open_url_returns(ctx: Ctx):
    """Where a breakaway frees the spawn (no outer Job, or one that lets it go) nothing changes: the start is quick
    and open_url says whether it took."""
    if not WIN:
        ctx.check("POSIX has no Job objects", True)
        return
    from halo_harness import closing
    from halo_harness import subprocess_safe

    class _Fails:
        def __init__(self, args, **kw):
            raise FileNotFoundError(args[0])

    with mock.patch.object(closing, "_in_a_job", lambda: True), \
            mock.patch.object(closing, "breakaway_frees", lambda: True), \
            mock.patch.object(subprocess_safe, "Popen", _Fails), \
            mock.patch.dict(os.environ, {"BROWSER": "no-such-browser.exe"}), \
            mock.patch.dict(closing._STATE, {"closed": False, "owner_gone": False, "hard_exit": None}):
        ok = closing.open_url("http://127.0.0.1:1/")
    ctx.check(f"a BROWSER that will not start: False at once, got {ok}", ok is False)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
