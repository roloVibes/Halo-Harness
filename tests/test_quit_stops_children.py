"""tests.test_quit_stops_children -- Halo 3.2.2.0 R3: a quit leaves no halo
behind. `Controller.quit` in a scoped home ends a fake registered background
run and the fake Studio `studio.json` names (never a real Studio: both are
`python -c "import time; time.sleep(60)"` children this file spawned), says
so in one line, and leaves a supervisor entry alone. The `-p` exit stops
only what that process registered.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once

ensure_scoped_state_dir_once()

from halo_harness import children as C
from tests.helpers.fake_remote_session import FakeRegistry, FakeSession

test, TESTS = new_registry()


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


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _fake_studio_json(state: Path, pid: int) -> Path:
    from halo_harness.studio.server import studio_info_path
    path = studio_info_path(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pid": pid, "port": _closed_port(), "token": "t", "pstart": C.start_time(pid)}),
                    encoding="utf-8")
    return path


@test
def test_controller_quit_ends_the_registered_run_and_the_studio_and_says_so(ctx: Ctx):
    from halo_harness.controller import Controller
    state = Path(tempfile.mkdtemp(prefix="r3-quit-"))
    studio, run, sup = _sleeper(), _sleeper(), _sleeper()
    try:
        info = _fake_studio_json(state, studio.pid)
        C.register(run.pid, "bg", [sys.executable, "-m", "halo_harness", "-p", "x"], state_dir=state, owner_pid=999999)
        C.register(sup.pid, "supervisor", ["halo", "supervise"], state_dir=state)
        controller = Controller(session=FakeSession(), cwd=state, registry=FakeRegistry(), state_dir=state)
        controller.quit()
        ctx.check("the fake Studio ended", _ended(studio))
        ctx.check("the fake background run ended", _ended(run))
        ctx.check("studio.json is gone", not info.exists())
        ctx.check(f"children.json keeps only the supervisor, got {C.load(state)}",
                  [r["what"] for r in C.load(state)] == ["supervisor"])
        ctx.check("the supervisor keeps running (it was started on purpose)", sup.poll() is None)
        line = controller.stopped_line
        ctx.check(f"one line names both, got {line!r}",
                  line.startswith("stopped: ") and f"Studio (pid {studio.pid})" in line
                  and f"background run (pid {run.pid})" in line
                  and line.endswith("; left running: supervisor (halo supervise stop)"))
        controller.quit_called = False
        controller.quit()
        ctx.check(f"a second quit stops nothing and names the supervisor it leaves, got {controller.stopped_line!r}",
                  controller.stopped_line == "left running: supervisor (halo supervise stop)")
    finally:
        _cleanup(studio, run, sup)


@test
def test_a_quit_with_nothing_running_says_nothing(ctx: Ctx):
    from halo_harness.controller import Controller
    state = Path(tempfile.mkdtemp(prefix="r3-quit-empty-"))
    controller = Controller(session=FakeSession(), cwd=state, registry=FakeRegistry(), state_dir=state)
    controller.quit()
    ctx.check(f"no line, and no 'left running', got {controller.stopped_line!r}", controller.stopped_line == ""
              and "left running" not in controller.stopped_line)


@test
def test_the_quit_line_names_what_it_left_running_with_the_command_that_ends_it(ctx: Ctx):
    """A `halo --bg` run from a plain shell (no owner) and the Studio while a
    second halo session of this home is open both stay; the line names them."""
    from halo_harness.controller import Controller
    from halo_harness.remote import registry
    state = Path(tempfile.mkdtemp(prefix="r3-quit-left-"))
    studio, shell_run, other_session = _sleeper(), _sleeper(), _sleeper()
    reg = registry.registry_path()
    saved = reg.read_text(encoding="utf-8") if reg.exists() else None
    try:
        _fake_studio_json(state, studio.pid)
        owner_env = os.environ.pop(C.OWNER_ENV, None)  # a plain shell: no halo session ran it
        C.register(shell_run.pid, "bg", [sys.executable, "-m", "halo_harness", "-p", "x"], state_dir=state,
                   launched=True, bg_id="ab12cd34")
        if owner_env is not None:
            os.environ[C.OWNER_ENV] = owner_env
        registry._write(reg, [{"session_id": "r3-second-session", "pid": other_session.pid, "kind": "tui",
                               "endpoint": "", "cwd": str(state)}])
        controller = Controller(session=FakeSession(), cwd=state, registry=FakeRegistry(), state_dir=state)
        controller.quit()
        line = controller.stopped_line
        ctx.check(f"one line names both, each with the command that ends it, got {line!r}",
                  line == "left running: 1 background run from a shell (halo bg stop ab12cd34), "
                          "Studio (another session is open; halo studio --stop)")
        ctx.check("and both really keep running", studio.poll() is None and shell_run.poll() is None)
    finally:
        if saved is None:
            reg.unlink(missing_ok=True)
        else:
            reg.write_text(saved, encoding="utf-8")
        C.unregister([shell_run.pid], state_dir=state)
        _cleanup(studio, shell_run, other_session)


@test
def test_a_stale_studio_json_pid_is_never_signalled(ctx: Ctx):
    """studio.json naming a pid whose start time no longer matches (the OS
    gave it to another program) is not a Studio: nothing is stopped."""
    from halo_harness.children_stop import stop_for_quit
    from halo_harness.studio.server import studio_info_path
    state = Path(tempfile.mkdtemp(prefix="r3-quit-stale-"))
    other = _sleeper()
    try:
        path = studio_info_path(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pid": other.pid, "port": _closed_port(), "token": "t", "pstart": "elsewhen"}),
                        encoding="utf-8")
        line = stop_for_quit(state, timeout=1.0)
        ctx.check(f"nothing named, got {line!r}", line == "")
        ctx.check("the other program keeps running", other.poll() is None)
    finally:
        _cleanup(other)


@test
def test_studio_stop_ends_the_studio_on_every_platform(ctx: Ctx):
    """`halo studio --stop`'s own path (launch.stop): the shutdown route
    does not answer, so the signal ends it -- by pid, proven by `pstart`
    (Windows has no /proc, which used to leave it running)."""
    from halo_harness.studio import launch
    state = Path(tempfile.mkdtemp(prefix="r3-studio-stop-"))
    studio = _sleeper()
    try:
        _fake_studio_json(state, studio.pid)
        ok, msg = launch.stop(state)
        ctx.check(f"stopped and said so, got {ok} {msg!r}", ok and f"pid {studio.pid}" in msg)
        ctx.check("the process ended", _ended(studio))
    finally:
        _cleanup(studio)


@test
def test_the_print_mode_exit_stops_only_its_own_children(ctx: Ctx):
    import contextlib
    import io
    from halo_harness import headless
    state = C._state(None)
    mine, theirs = _sleeper(), _sleeper()
    try:
        C.register(mine.pid, "schedule", ["python"])
        C.register(theirs.pid, "schedule", ["python"], owner_pid=theirs.pid)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            headless._stop_own_children_quietly()
        ctx.check(f"one stderr line names this process's child, got {err.getvalue()!r}",
                  err.getvalue().strip() == f"halo: stopped: schedule fire (pid {mine.pid})")
        ctx.check("its child ended; the other owner's runs on", _ended(mine) and theirs.poll() is None)
        ctx.check("the real ~/.halo is not the state dir here", Path(state).resolve() != (Path.home() / ".halo").resolve())
    finally:
        C.unregister([mine.pid, theirs.pid])
        _cleanup(mine, theirs)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
