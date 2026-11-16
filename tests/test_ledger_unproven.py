"""tests.test_ledger_unproven -- Halo 3.6.0.1: a ledger row Halo cannot prove is its own (no start time recorded).

- the reader rule: a row with no start time whose pid now runs a process that started AFTER the row was written is
  another program's (children.newer_than_row): `prune`, `halo ps` and `/update` drop it; one that may be Halo's stays
- `halo ps --forget <pid>`: removes such a record and signals nothing; refuses a pid proven Halo's
- the Windows `/update` refusal names `--forget` for a ledger row only and never a bare `taskkill` / `kill`
- the writer: no row for a pid already gone; a start time read again while unreadable; a known one passed in
- `halo update` / `/update` confirm a scanned pid (and an opener, and the supervisor's pulse pid) after reading its
  start time, so a pid reused in between never lends another program's start time to the plan

Every process here is a stand-in this file starts (`python -c "import time; time.sleep(60)"`) and ends in a
`finally`; process lists are fakes; nothing real is listed, signalled or installed.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import bg_run
from halo_harness import children as C
from halo_harness import ps_cli
from halo_harness import update as upd
from halo_harness import update_detached as UD
from halo_harness import update_plan as UP
from halo_harness import update_stop

test, TESTS = new_registry()
HOUR = 3600.0


def _state() -> Path:
    return Path(tempfile.mkdtemp(prefix="v3601-ledger-"))


def _sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _cleanup(*procs) -> None:
    for p in procs:
        if p.poll() is None:
            p.kill()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass


def _linux_proc() -> bool:
    return os.name != "nt" and not bg_run.no_proc()


def _row(pid: int, shift: float, *, boot: bool = True, what: str = "shell") -> dict:
    """A row with no start time, written `shift` seconds from now (negative: an hour before the live process)."""
    row = {"pid": pid, "start_time": None, "what": what, "cmd": ["bash", "-c", "make"], "owner_pid": None,
           "owner_start": None, "since": round(time.time() + shift, 3)}
    if boot and _linux_proc():
        row["since_boot"] = round(time.clock_gettime(time.CLOCK_BOOTTIME) + shift, 3)
    return row


def _write_rows(state: Path, rows: list) -> None:
    (state / "run").mkdir(parents=True, exist_ok=True)
    C._write(C.registry_path(state), rows)


def _hand_off(state: Path, *, scan=None) -> "tuple[int, str, list]":
    """update_detached.run_after_exit(windows=True) with every outside step faked: (code, its text, plans)."""
    plans = []
    saved = (UD.reinstall_cmd, UD.launch, upd.halo_ancestors, upd.halo_openers, update_stop.scanned,
             UP.outside_python, upd._direct_url)
    UD.reinstall_cmd = lambda to=None: ("echo x", {"kind": "uv_tool", "spec": "git+https://x"})
    UD.launch = lambda plan, **kw: plans.append(plan) or 0
    upd.halo_ancestors = lambda **kw: []
    upd.halo_openers = lambda **kw: []
    update_stop.scanned = lambda known=(): list(scan or [])
    UP.outside_python = lambda: ["/opt/py/python3", "-I"]
    upd._direct_url = lambda: None
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = UD.run_after_exit(state_dir=state, windows=True)
    finally:
        (UD.reinstall_cmd, UD.launch, upd.halo_ancestors, upd.halo_openers, update_stop.scanned,
         UP.outside_python, upd._direct_url) = saved
    return code, out.getvalue() + err.getvalue(), plans


@test
def test_start_epoch_reads_a_filetime_and_a_utc_ps_text(ctx: Ctx):
    ft = bg_run.start_epoch("133000000000000000", windows=True)
    ctx.check(f"a FILETIME is seconds since 1601, got {ft}", ft == 133000000000000000 / 1e7 - 11644473600)
    import calendar
    ps = bg_run.start_epoch("ps:Mon Oct  5 10:00:00 2026")
    ctx.check(f"a ps: lstart (day padded) is read as UTC, got {ps}", ps == calendar.timegm((2026, 10, 5, 10, 0, 0)))
    ctx.check("Linux ticks are not wall time here", bg_run.start_epoch("12345", windows=False) is None)
    ctx.check("unreadable texts give None", bg_run.start_epoch("ps:garbage") is None and bg_run.start_epoch(None) is None)


@test
def test_a_row_with_no_start_time_whose_pid_started_later_is_dropped_by_every_reader(ctx: Ctx):
    state = _state()
    other = _sleeper()  # "another program" the OS gave the pid to, an hour after the row was written
    try:
        _write_rows(state, [_row(other.pid, -HOUR)])
        ctx.check(f"prune drops it, got {C.prune(state)}", C.prune(state) == [] and C.load(state) == [])
        _write_rows(state, [_row(other.pid, -HOUR)])
        listed = [r["pid"] for r in ps_cli.rows(state)]
        ctx.check(f"halo ps does not list it, got {listed}", other.pid not in listed)
        _write_rows(state, [_row(other.pid, -HOUR)])
        code, text, plans = _hand_off(state)
        ctx.check(f"/update on Windows does not refuse on it, got {code} {text!r}",
                  code == 0 and "not installing" not in text and plans and other.pid not in plans[0]["stop_pids"])
        ctx.check("the other program was never signalled", other.poll() is None)
    finally:
        _cleanup(other)


@test
def test_a_row_with_no_start_time_that_may_be_halos_is_kept_and_never_signalled(ctx: Ctx):
    state = _state()
    proc = _sleeper()
    try:
        _write_rows(state, [_row(proc.pid, +HOUR)])  # written after the process started: it may be Halo's
        ctx.check(f"prune keeps it, got {C.prune(state)}", [r["pid"] for r in C.prune(state)] == [proc.pid])
        code, text, plans = _hand_off(state)
        ctx.check(f"/update on Windows refuses, got {code} {text!r}", code == 1 and "not installing" in text)
        ctx.check(f"the refusal names `halo ps --forget {proc.pid}` and no bare signal, got {text!r}",
                  f"halo ps --forget {proc.pid}" in text and "taskkill" not in text and f"kill {proc.pid}" not in text)
        ctx.check("nothing was signalled", proc.poll() is None and not plans)
        if _linux_proc():  # a Linux row written before 3.6.0.1 has no since_boot: not provable, kept
            _write_rows(state, [_row(proc.pid, -HOUR, boot=False)])
            ctx.check("a Linux row without since_boot is kept", [r["pid"] for r in C.prune(state)] == [proc.pid])
    finally:
        _cleanup(proc)


@test
def test_the_refusal_names_forget_only_for_a_ledger_row(ctx: Ctx):
    state = _state()
    proc = _sleeper()
    try:
        scan = [{"pid": proc.pid, "start_time": None, "what": "halo", "cmd": ["halo"], "source": "scan"}]
        code, text, _plans = _hand_off(state, scan=scan)
        ctx.check(f"a scanned halo with no start time: refused, no --forget, no bare signal, got {code} {text!r}",
                  code == 1 and "--forget" not in text and "taskkill" not in text and f"pid {proc.pid}" in text)
    finally:
        _cleanup(proc)


@test
def test_halo_ps_forget_removes_the_record_and_signals_nothing(ctx: Ctx):
    state = _state()
    proc, mine = _sleeper(), _sleeper()
    try:
        _write_rows(state, [_row(proc.pid, +HOUR)])
        C.register(mine.pid, "bg", ["python"], state_dir=state)  # proven: its start time recorded
        forgot, refused = ps_cli.forget([proc.pid], state_dir=state)
        ctx.check(f"forgotten, one line naming kind and pid, got {forgot} {refused}",
                  not refused and len(forgot) == 1 and f"shell command (pid {proc.pid})" in forgot[0]["line"]
                  and "nothing was signalled" in forgot[0]["line"])
        ctx.check("the row is gone, the proven one stays", [r["pid"] for r in C.load(state)] == [mine.pid])
        ctx.check("the process still runs", proc.poll() is None)
        forgot, refused = ps_cli.forget([mine.pid], state_dir=state)
        ctx.check(f"a running process proven Halo's is refused with `halo stop`, got {refused}",
                  not forgot and refused and f"halo stop {mine.pid}" in refused[0]["line"]
                  and [r["pid"] for r in C.load(state)] == [mine.pid] and mine.poll() is None)
        forgot, refused = ps_cli.forget([proc.pid], state_dir=state)
        ctx.check(f"a pid not in the ledger is refused, got {refused}",
                  not forgot and "nothing of Halo here is pid" in refused[0]["line"])
        saved = ps_cli._sessions
        ps_cli._sessions = lambda home: [{"pid": proc.pid}]
        try:
            forgot, refused = ps_cli.forget([proc.pid], state_dir=state)
        finally:
            ps_cli._sessions = saved
        ctx.check(f"a session is refused, got {refused}", not forgot and "is a session" in refused[0]["line"])
        servers = [{"model": "m1", "pid": proc.pid, "runtime": "llama-server", "cmdline": ["llama-server"],
                    "proc_start": None, "started": datetime.now(timezone.utc).isoformat()}]
        (state / "run" / "local-servers.json").write_text(json.dumps(servers), encoding="utf-8")
        forgot, refused = ps_cli.forget([proc.pid], state_dir=state)
        left = json.loads((state / "run" / "local-servers.json").read_text(encoding="utf-8"))
        ctx.check(f"a model server's record is forgotten in its own registry, got {forgot} {refused} {left}",
                  forgot and not refused and left == [] and proc.poll() is None)
    finally:
        _cleanup(proc, mine)


@test
def test_halo_ps_takes_forget(ctx: Ctx):
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = ps_cli.cmd_ps(["--forget", "999999999"])
    except SystemExit as e:
        code = f"argparse exit {e.code}"
    ctx.check(f"`halo ps --forget <pid>` is accepted and refuses a pid not in the ledger, got {code} {err.getvalue()!r}",
              code == 1 and "nothing of Halo here is pid 999999999" in err.getvalue())


@test
def test_register_writes_no_row_for_a_pid_already_gone(ctx: Ctx):
    import gc
    state = _state()
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait(timeout=30)
    pid = gone.pid
    del gone
    gc.collect()
    got = C.register(pid, "studio", ["halo", "studio"], state_dir=state)
    ctx.check(f"register returns None and writes nothing, got {got} {C.load(state)}", got is None and C.load(state) == [])


@test
def test_register_reads_an_unreadable_start_again_and_takes_a_known_one(ctx: Ctx):
    state = _state()
    proc = _sleeper()
    saved = C.start_time
    answers = [None, None, "LATE"]
    try:
        C.start_time = lambda pid: (answers.pop(0) if answers else "LATE") if pid == proc.pid else saved(pid)
        entry = C.register(proc.pid, "bg", ["python"], state_dir=state)
        ctx.check(f"read again while it runs, got {entry}", entry and entry["start_time"] == "LATE")
        C.start_time = lambda pid: "READ" if pid == proc.pid else saved(pid)
        entry = C.register(proc.pid, "bg", ["python"], state_dir=state, start="123", owner_start="456")
        ctx.check(f"a known start time is recorded as given, got {entry}",
                  entry and entry["start_time"] == "123" and entry["owner_start"] == "456")
        if _linux_proc():
            ctx.check("Linux rows carry since_boot", isinstance(entry.get("since_boot"), float))
    finally:
        C.start_time = saved
        _cleanup(proc)


@test
def test_the_studio_row_takes_the_start_time_studio_json_carries(ctx: Ctx):
    from halo_harness import closing
    from halo_harness.studio import launch
    state = _state()
    launcher, studio = _sleeper(), _sleeper()
    try:
        me, me_start = closing.me()
        (state / "studio.json").write_text(json.dumps({"pid": studio.pid, "pstart": "PSTART-123", "port": 8123,
                                                       "owner_pid": me, "owner_start": me_start}), encoding="utf-8")
        launch._ledger_names_the_studio(launcher, ["halo", "studio"], state)
        rows = {r["pid"]: r for r in C.load(state)}
        ctx.check(f"the row carries studio.json's pstart, got {rows}",
                  studio.pid in rows and rows[studio.pid]["start_time"] == "PSTART-123")
    finally:
        _cleanup(launcher, studio)


def _scripted_list(first: str, later: str):
    calls = []

    def fake(*, run_fn=None, windows=None):
        calls.append(1)
        return [(4242, 1, first if len(calls) == 1 else later)]
    return fake, calls


@test
def test_a_scanned_pid_reused_before_its_start_time_is_read_is_dropped(ctx: Ctx):
    saved = (upd.list_processes, C.start_time)
    try:
        C.start_time = lambda pid: "NEW-PROGRAM"
        upd.list_processes, calls = _scripted_list("/usr/bin/python3 -m halo_harness supervise", "notepad.exe")
        got = update_stop.scanned()
        ctx.check(f"the reused pid is not returned at all, got {got}", all(r["pid"] != 4242 for r in got))
        same = "/usr/bin/python3 -m halo_harness supervise"
        upd.list_processes, calls = _scripted_list(same, same)
        got = update_stop.scanned()
        ctx.check(f"a pid still running the listed command is kept with its start time, got {got}",
                  [(r["pid"], r["start_time"]) for r in got] == [(4242, "NEW-PROGRAM")])
    finally:
        upd.list_processes, C.start_time = saved


@test
def test_an_opener_reused_before_its_start_time_is_read_never_reaches_the_plan(ctx: Ctx):
    state = _state()
    me = os.getpid()
    calls = []

    def fake(*, run_fn=None, windows=None):
        calls.append(1)
        top = "/usr/bin/python3 -m halo_harness studio" if len(calls) == 1 else "notepad.exe"
        return [(me, 4242, "python -m halo_harness"), (4242, 1, top)]
    saved = (upd.list_processes, C.start_time, UD.reinstall_cmd, UD.launch, upd.halo_ancestors, update_stop.scanned,
             UP.outside_python, upd._direct_url)
    plans = []
    try:
        upd.list_processes = fake
        C.start_time = lambda pid: "NEW-PROGRAM" if pid == 4242 else None
        UD.reinstall_cmd = lambda to=None: ("echo x", {"kind": "uv_tool", "spec": "git+https://x"})
        UD.launch = lambda plan, **kw: plans.append(plan) or 0
        upd.halo_ancestors = lambda **kw: []
        update_stop.scanned = lambda known=(): []
        UP.outside_python = lambda: ["/opt/py/python3", "-I"]
        upd._direct_url = lambda: None
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = UD.run_after_exit(state_dir=state, windows=True)
        ctx.check(f"no line names 4242 and the plan has no 4242, got {code} {out.getvalue()!r} {plans}",
                  code == 0 and "4242" not in out.getvalue() and plans and 4242 not in plans[0]["stop_pids"]
                  and 4242 not in plans[0].get("stop_starts", {}))
    finally:
        (upd.list_processes, C.start_time, UD.reinstall_cmd, UD.launch, upd.halo_ancestors, update_stop.scanned,
         UP.outside_python, upd._direct_url) = saved


@test
def test_the_supervisor_pulse_pid_is_confirmed_before_it_reaches_the_plan(ctx: Ctx):
    from halo_harness.remote import proc_ident
    from halo_harness.supervise import pulse
    proc = _sleeper()
    saved = (pulse.read, pulse.read_row)
    try:
        def use(pid, pstart):
            pulse.read = lambda state_dir=None: {"running": True, "pid": pid, "state": "running"}
            pulse.read_row = lambda state_dir=None: {"pid": pid, "pstart": pstart}
            return update_stop._supervisor_entry(_state())
        got = use(proc.pid, "win:1" if os.name == "nt" else "ps:Thu Jan  1 00:00:01 1970")
        ctx.check(f"a pulse pid now running another program is dropped, got {got}", got is None)
        dead = subprocess.Popen([sys.executable, "-c", "pass"])
        dead.wait(timeout=30)
        got = use(dead.pid, "win:1")
        ctx.check(f"a pulse pid that vanished is dropped, got {got}", got is None)
        got = use(proc.pid, proc_ident.start_token(proc.pid))
        ctx.check(f"the process that wrote the pulse keeps its own start time, got {got}",
                  got and got["start_time"] == C.start_time(proc.pid))
        ctx.check("nothing was signalled", proc.poll() is None)
    finally:
        pulse.read, pulse.read_row = saved
        _cleanup(proc)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
