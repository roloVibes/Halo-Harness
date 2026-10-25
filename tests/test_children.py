"""tests.test_children -- Halo 3.2.2.0 R3: the children registry
(`~/.halo/run/children.json`, halo_harness/children.py) and its stop paths
(children_stop.py). Every process here is a fake child this file spawned
(`python -c "import time; time.sleep(60)"`) in a scoped state dir; nothing
real is ever listed or stopped.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import children as C
from halo_harness import children_stop as CS

test, TESTS = new_registry()


def _state() -> Path:
    return Path(tempfile.mkdtemp(prefix="r3-children-"))


def _sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _ended(proc: subprocess.Popen, within: float = 10.0) -> bool:
    try:
        proc.wait(timeout=within)
        return True
    except subprocess.TimeoutExpired:
        return False


def _cleanup(*procs) -> None:
    for p in procs:
        if p.poll() is None:
            p.kill()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


@test
def test_register_records_pid_start_time_owner_and_prune_drops_the_gone(ctx: Ctx):
    state = _state()
    a, b = _sleeper(), _sleeper()
    try:
        entry = C.register(a.pid, "bg", [sys.executable, "-m", "halo_harness", "-p", "x"], state_dir=state, bg_id="r1")
        C.register(b.pid, "schedule", ["python", "-m", "halo_harness", "-p", "y"], state_dir=state)
        ctx.check(f"the entry carries pid, start time, what, cmd, owner, since, got {entry}",
                  entry and entry["pid"] == a.pid and entry["start_time"] and entry["what"] == "bg"
                  and entry["owner_pid"] == os.getpid() and entry["since"] and entry["bg_id"] == "r1")
        data = json.loads(C.registry_path(state).read_text(encoding="utf-8"))
        ctx.check(f"children.json holds both, got {data}", sorted(r["pid"] for r in data["children"]) == sorted([a.pid, b.pid]))
        b.kill()
        b.wait(timeout=10)
        live = C.prune(state)
        ctx.check(f"prune drops the ended child and keeps the live one, got {live}",
                  [r["pid"] for r in live] == [a.pid] and [r["pid"] for r in C.load(state)] == [a.pid])
    finally:
        _cleanup(a, b)


@test
def test_a_reused_pid_is_told_apart_by_its_start_time_and_never_stopped(ctx: Ctx):
    state = _state()
    proc = _sleeper()
    try:
        C.register(proc.pid, "schedule", ["python"], state_dir=state)
        rows = C.load(state)
        rows[0]["start_time"] = "another-program-started-then"
        C._write(C.registry_path(state), rows)
        ctx.check("an entry whose start time differs is not alive", not C.alive(rows[0]))
        lines = CS.stop_all(state_dir=state, timeout=1.0)
        ctx.check(f"stop_all signals nothing for it, got {lines}", lines == [])
        ctx.check("the process that now has that pid keeps running", proc.poll() is None)
        ctx.check(f"and the stale entry is gone from the file, got {C.load(state)}", C.load(state) == [])
    finally:
        _cleanup(proc)


@test
def test_stop_all_ends_registered_children_one_line_each(ctx: Ctx):
    state = _state()
    a, b = _sleeper(), _sleeper()
    try:
        C.register(a.pid, "schedule", ["python"], state_dir=state)
        C.register(b.pid, "bg", ["python"], state_dir=state)
        lines = CS.stop_all(state_dir=state, timeout=3.0)
        ctx.check(f"one line per process, got {lines}", sorted(lines) == sorted(
            [f"stopped: schedule fire (pid {a.pid})", f"stopped: background run (pid {b.pid})"]))
        ctx.check("both processes ended", _ended(a) and _ended(b))
        ctx.check(f"and children.json is empty, got {C.load(state)}", C.load(state) == [])
    finally:
        _cleanup(a, b)


@test
def test_stop_all_with_an_owner_stops_only_that_owners(ctx: Ctx):
    state = _state()
    mine, theirs = _sleeper(), _sleeper()
    try:
        C.register(mine.pid, "schedule", ["python"], state_dir=state)
        C.register(theirs.pid, "schedule", ["python"], state_dir=state, owner_pid=theirs.pid)
        lines = CS.stop_all(os.getpid(), timeout=3.0, state_dir=state)
        ctx.check(f"only this process's child, got {lines}", lines == [f"stopped: schedule fire (pid {mine.pid})"])
        ctx.check("mine ended, theirs runs on", _ended(mine) and theirs.poll() is None)
    finally:
        _cleanup(mine, theirs)


@test
def test_a_quit_leaves_the_supervisor_and_a_live_owners_children_alone(ctx: Ctx):
    state = _state()
    sup, other, orphan = _sleeper(), _sleeper(), _sleeper()
    owner = _sleeper()  # stands for another process (the supervisor) that started a run
    try:
        C.register(sup.pid, "supervisor", ["halo", "supervise"], state_dir=state)
        C.register(other.pid, "bg", ["python"], state_dir=state, owner_pid=owner.pid)
        C.register(orphan.pid, "schedule", ["python"], state_dir=state, owner_pid=999999)
        line = CS.stop_for_quit(state, timeout=3.0)
        ctx.check(f"the quit stops only the orphan and names what it left, got {line!r}",
                  line == f"stopped: schedule fire (pid {orphan.pid}); left running: 1 background run of a running halo "
                          f"(it ends with pid {owner.pid}), supervisor (halo supervise stop)")
        ctx.check("the orphan (its owner is gone) ended", _ended(orphan))
        ctx.check("the supervisor and the live owner's run keep running", sup.poll() is None and other.poll() is None)
    finally:
        _cleanup(sup, other, orphan, owner)


@test
def test_a_bg_run_from_a_plain_shell_outlives_a_quit_but_not_an_update_stop(ctx: Ctx):
    """`halo --bg` from a shell (no HALO_OWNER_PID) belongs to no session; from
    a session's Bash tool (HALO_OWNER_PID = that session) it ends with it."""
    state = _state()
    shell_run, session_run = _sleeper(), _sleeper()
    saved = os.environ.pop(C.OWNER_ENV, None)
    try:
        e1 = C.register(shell_run.pid, "bg", ["python"], launched=True, state_dir=state)
        os.environ[C.OWNER_ENV] = str(os.getpid())
        e2 = C.register(session_run.pid, "bg", ["python"], launched=True, state_dir=state)
        ctx.check(f"owners: none for the shell, this session for the tool, got {e1['owner_pid']} {e2['owner_pid']}",
                  e1["owner_pid"] is None and e2["owner_pid"] == os.getpid())
        line = CS.stop_for_quit(state, timeout=3.0)
        ctx.check(f"the quit ends the session's run only, got {line!r}",
                  line == f"stopped: background run (pid {session_run.pid}); left running: 1 background run from a shell "
                          f"(halo bg list, then halo bg stop <id>)" and _ended(session_run)
                  and shell_run.poll() is None)
        ctx.check("stop_all (what `halo update` uses) ends the shell's run too",
                  CS.stop_all(state_dir=state, timeout=3.0) == [f"stopped: background run (pid {shell_run.pid})"]
                  and _ended(shell_run))
    finally:
        os.environ.pop(C.OWNER_ENV, None)
        if saved is not None:
            os.environ[C.OWNER_ENV] = saved
        _cleanup(shell_run, session_run)


@test
def test_the_summary_is_one_line(ctx: Ctx):
    rows = [{"what": "studio", "pid": 4242, "ok": True}, {"what": "bg", "pid": 11, "ok": True},
            {"what": "bg", "pid": 12, "ok": True}]
    ctx.check(f"Studio by pid, two runs by count, got {CS.summary(rows)!r}",
              CS.summary(rows) == "stopped: Studio (pid 4242), 2 background runs")
    ctx.check("nothing ran: nothing to say", CS.summary([]) == "")
    left = CS.summary([{"what": "schedule", "pid": 7, "ok": False}])
    ctx.check(f"a process that did not end is named as still running, got {left!r}",
              left == "still running: schedule fire (pid 7)")


@test
def test_a_registry_problem_never_stops_a_spawn(ctx: Ctx):
    state = _state()
    (state / "run").mkdir(parents=True)
    C.registry_path(state).write_text("{not json", encoding="utf-8")
    ctx.check("a broken children.json reads as empty", C.load(state) == [])
    ctx.check("register on a bad pid returns None, no raise", C.register(-1, "bg", [], state_dir=state) is None)
    ctx.check("prune of a missing registry is []", C.prune(_state()) == [])


@test
def test_local_servers_are_read_from_their_own_registry(ctx: Ctx):
    state = _state()
    (state / "run").mkdir(parents=True)
    rows = [{"model": "m1", "pid": 101, "runtime": "mlx_lm", "cmdline": [str(Path(sys.prefix) / "python"), "-m", "mlx_lm.server"],
             "proc_start": "1", "owner_pid": 5},
            {"model": "m2", "pid": 102, "runtime": "llama-server", "cmdline": ["/opt/llama/llama-server"], "keep": True}]
    (state / "run" / "local-servers.json").write_text(json.dumps(rows), encoding="utf-8")
    got = C.local_servers(state)
    ctx.check(f"both rows in this module's shape, got {got}", [(r["pid"], r["what"], r["model"]) for r in got]
              == [(101, "mlx", "m1"), (102, "llama", "m2")] and got[1]["keep"] is True)
    venv = C.local_servers(state, venv_only=True)
    ctx.check(f"venv_only keeps the one on this install's python, got {venv}", [r["pid"] for r in venv] == [101])
    ctx.check("and the local-servers file is untouched", json.loads((state / "run" / "local-servers.json").read_text()) == rows)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
