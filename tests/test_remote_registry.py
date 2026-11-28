"""tests.test_remote_registry -- Halo 2.0.9 round 2: `~/.halo/run/sessions.json`
(atomic write, dead-pid sweep, connect-probe sweep, title and mode refresh,
`halo remote sessions`), and that other files in the run dir (a stray
`*.sock` an older Halo left, `local-servers.json`) are left alone.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.remote_rig import Rig
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


class _Home:
    def __init__(self):
        self._saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
        os.environ.pop("BRIDGE_STATE_DIR", None)
        os.environ["BRIDGE_TEST_HOME"] = tempfile.mkdtemp(prefix="remote-reg-")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return False


class _Listener:
    """A loopback listener standing in for a live session's endpoint."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.endpoint = f"tcp:127.0.0.1:{self.sock.getsockname()[1]}"

    def close(self):
        self.sock.close()


def _entry(sid, endpoint, pid=None, **kw):
    from halo_harness.remote import registry
    return registry.make_entry(session_id=sid, cwd="/work/x", endpoint=endpoint, pid=pid, **kw)


@test
def test_entry_shape_and_atomic_write(ctx: Ctx):
    from halo_harness.remote import registry
    with _Home():
        lst = _Listener()
        registry.register(_entry("s1", lst.endpoint, title="first", mode="default"))
        path = registry.registry_path()
        data = json.loads(path.read_text("utf-8"))
        row = data["sessions"][0]
        ctx.check("entry fields are exactly the brief's (plus kind)",
                  {"session_id", "cwd", "pid", "endpoint", "token_env", "started", "title", "mode"} <= set(row)
                  and row["token_env"] is None and row["pid"] == os.getpid())
        ctx.check("no temp files left beside the registry", [p.name for p in path.parent.glob(".sessions.json.*")] == [])
        if os.name != "nt":
            ctx.check("sessions.json is 0600", (path.stat().st_mode & 0o777) == 0o600)

        def _reg(i):
            registry.register(_entry(f"t{i}", lst.endpoint))
        threads = [threading.Thread(target=_reg, args=(i,)) for i in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        ids = {r["session_id"] for r in json.loads(path.read_text("utf-8"))["sessions"]}
        ctx.check("8 concurrent registers under the lock lost nothing", ids == {"s1"} | {f"t{i}" for i in range(8)})
        registry.register(_entry("s1", lst.endpoint, title="again"))
        rows = json.loads(path.read_text("utf-8"))["sessions"]
        ctx.check("re-registering a session replaces its entry", [r["title"] for r in rows if r["session_id"] == "s1"] == ["again"])
        registry.unregister("s1")
        ctx.check("unregister removes it", all(r["session_id"] != "s1" for r in json.loads(path.read_text("utf-8"))["sessions"]))
        lst.close()


@test
def test_dead_pid_and_dead_endpoint_are_swept(ctx: Ctx):
    from halo_harness.remote import registry
    with _Home():
        live, dead_pid_listener = _Listener(), _Listener()
        gone = _Listener()
        gone_endpoint = gone.endpoint
        gone.close()  # nothing listens here any more
        real = registry.pid_alive
        registry.pid_alive = lambda pid: pid != 424242
        try:
            registry.register(_entry("alive", live.endpoint))
            registry.register(_entry("deadpid", dead_pid_listener.endpoint, pid=424242))
            registry.register(_entry("deadsock", gone_endpoint))
            # 3.6.0.4: a refused endpoint is "not answering now" (kept, marked); it leaves after 30 s of refusals
            ctx.check("endpoint_for keeps a refused one at first", registry.endpoint_for("deadsock") == gone_endpoint)
            ids = {r["session_id"] for r in json.loads(registry.registry_path().read_text("utf-8"))["sessions"]}
            ctx.check(f"dead pid removed from the file at once, got {ids}", ids == {"alive", "deadsock"})
            later = registry.time.time() + registry.UNREACHABLE_PRUNE_S + 1
            ctx.check("30 s of refusals later only the live one is listed",
                      [r["session_id"] for r in registry.list_live(now=later)] == ["alive"])
            ids = {r["session_id"] for r in json.loads(registry.registry_path().read_text("utf-8"))["sessions"]}
            ctx.check(f"and the file keeps only the live one, got {ids}", ids == {"alive"})
            ctx.check("endpoint_for finds the live one", registry.endpoint_for("alive") == live.endpoint)
        finally:
            registry.pid_alive = real
            live.close()
            dead_pid_listener.close()


@test
def test_a_slow_tasklist_never_sweeps_a_live_session(ctx: Ctx):
    """3.4.1.0 R6: on the Windows runner one `tasklist` past bg_run.pid_alive's 5 s timeout read a live session as
    dead and list_live pruned it for good. The registry asks the process itself now (here: every tasklist times out)."""
    import subprocess
    from halo_harness import bg_run
    from halo_harness.remote import registry
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], stdin=subprocess.DEVNULL)
    real_run = bg_run.subprocess.run

    def slow(args, *a, **kw):
        if isinstance(args, list) and args and args[0] == "tasklist":
            raise subprocess.TimeoutExpired(args, kw.get("timeout") or 5)
        return real_run(args, *a, **kw)
    with _Home():
        lst = _Listener()
        bg_run.subprocess.run = slow
        try:
            registry.register(_entry("mine", lst.endpoint))
            registry.register(_entry("child", lst.endpoint, pid=child.pid))
            ids = sorted(r["session_id"] for r in registry.list_live())
            ctx.check(f"this process's session and a running child's stay listed, got {ids}", ids == ["child", "mine"])
            child.kill()
            child.wait(timeout=10)
            ids = sorted(r["session_id"] for r in registry.list_live())
            ctx.check(f"the child gone, its row is swept, got {ids}", ids == ["mine"])
        finally:
            bg_run.subprocess.run = real_run
            lst.close()
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)


@test
def test_other_run_dir_files_are_untouched(ctx: Ctx):
    from halo_harness.remote import registry
    from halo_harness.remote.control_socket import run_dir
    with _Home():
        d = run_dir()
        cc = d / "0123456789abcdef0123456789abcdef.sock"
        cc.write_text("not a socket", encoding="utf-8")
        local = d / "local-servers.json"
        local.write_text("{}", encoding="utf-8")
        registry.register(_entry("x", _Listener().endpoint))
        registry.list_live()
        registry.sweep_stale_ctl(d)
        ctx.check("a stray *.sock and local-servers.json survive the registry sweep",
                  cc.exists() and local.exists())


@test
def test_title_and_mode_refresh_and_cli(ctx: Ctx):
    from halo_harness.cli import main
    from halo_harness.remote import registry, runtime
    from halo_harness.theme import set_config_value
    with Rig(serve=False) as rig:
        set_config_value("remote.enabled", True)
        act = runtime.start_for_controller(rig.controller)
        sid = rig.session.log.session_id
        row = registry.entry_for(sid)
        ctx.check("registered with no title yet", row is not None and row["title"] == "")
        rig.controller.rename_session("Fix the flaky test")
        ctx.check("rename_session (the auto-title path) refreshes the title",
                  registry.entry_for(sid)["title"] == "Fix the flaky test")
        rig.controller.set_permission_mode("plan")
        ctx.check("a mode change refreshes the mode", registry.entry_for(sid)["mode"] == "plan")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["remote", "sessions"])
        out = buf.getvalue()
        ctx.check("halo remote sessions lists this session", code == 0 and sid[:8] in out and act.endpoint in out
                  and "Fix the flaky test" in out and "plan" in out)
        tok = act.server.token
        ctx.check("the listing never prints the token", not tok or tok not in out)
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["remote", "bogus"])
        ctx.check("an unknown remote subcommand is a usage error", code == 2)
        rig.controller.quit()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            main(["remote", "sessions"])
        ctx.check("after quit the session is gone from the listing", sid[:8] not in buf.getvalue())


class _Probe:
    """client.probe stand-in: answers from `answers` in turn, then `rest`."""

    def __init__(self, answers=(), rest=True):
        from halo_harness.remote import client
        self.client, self.real, self.answers, self.rest = client, client.probe, list(answers), rest
        client.probe = self

    def __call__(self, endpoint, *a, **kw):
        return self.answers.pop(0) if self.answers else self.rest

    def close(self):
        self.client.probe = self.real


def _file_rows():
    from halo_harness.remote import registry
    return {r["session_id"]: r for r in json.loads(registry.registry_path().read_text("utf-8"))["sessions"]}


@test
def test_one_failed_probe_keeps_the_row_and_marks_it(ctx: Ctx):
    """3.6.0.4 S1: one refused connect (a full accept queue) pruned a running session's row for good and Studio lost
    it. Now the row stays, listed, with `unreachable_since`; the next good probe clears the mark."""
    from halo_harness.remote import registry
    with _Home():
        lst = _Listener()
        probe = _Probe(answers=[False])
        try:
            registry.register(_entry("s1", lst.endpoint))
            got = registry.list_live()  # as every caller calls it
            ctx.check(f"one failed probe: still listed, got {[r['session_id'] for r in got]}",
                      [r["session_id"] for r in got] == ["s1"])
            since = got[0].get("unreachable_since")
            ctx.check(f"the listed row carries the first failure's time, got {since}", isinstance(since, float))
            ctx.check("and so does the file", _file_rows().get("s1", {}).get("unreachable_since") == since)
            got = registry.list_live()
            ctx.check("the next good probe lists it without the mark",
                      [r["session_id"] for r in got] == ["s1"] and "unreachable_since" not in got[0])
            ctx.check("and the file loses the mark", "unreachable_since" not in _file_rows()["s1"])
        finally:
            probe.close()
            lst.close()


@test
def test_failing_for_30_s_prunes_and_every_reader_counts_from_the_first_failure(ctx: Ctx):
    from halo_harness.remote import registry
    with _Home():
        lst = _Listener()
        probe = _Probe(rest=False)
        real_alive = registry.pid_alive
        registry.pid_alive = lambda pid: pid != 424242
        try:
            registry.register(_entry("hung", lst.endpoint))
            registry.register(_entry("deadpid", lst.endpoint, pid=424242))
            got = [r["session_id"] for r in registry.list_live(now=1000.0)]
            ctx.check(f"a dead pid leaves at once, a refused one stays, got {got}", got == ["hung"])
            ctx.check("the dead pid's row is gone from the file", set(_file_rows()) == {"hung"})
            other = registry.list_live(now=1010.0)  # another process's reader, its own clock
            ctx.check(f"a second reader keeps the first failure's time, got {other[0].get(registry.UNREACHABLE)}",
                      other[0].get(registry.UNREACHABLE) == 1000.0
                      and _file_rows()["hung"].get(registry.UNREACHABLE) == 1000.0)
            ctx.check("29.9 s of failures: still listed",
                      [r["session_id"] for r in registry.list_live(now=1029.9)] == ["hung"])
            ctx.check("30 s of failures without one success: gone", registry.list_live(now=1030.0) == [])
            ctx.check("and gone from the file", _file_rows() == {})
        finally:
            registry.pid_alive = real_alive
            probe.close()
            lst.close()


@test
def test_a_mark_in_the_future_counts_as_set_now(ctx: Ctx):
    """3.6.0.4 S4-3: the first failure's time is a wall-clock time kept in the row; when the clock is set back after
    it was written, `now - unreachable_since` is negative and a refusing row stayed listed by the size of the step.
    A mark in the future is rewritten to now (in the same locked write), so the 30 s count starts again from there."""
    from halo_harness.remote import registry
    with _Home():
        lst = _Listener()
        probe = _Probe(rest=False)
        try:
            row = _entry("stepped", lst.endpoint)
            row[registry.UNREACHABLE] = 2000.0  # written before the clock was set back by 1000 s
            registry.register(row)
            got = [r["session_id"] for r in registry.list_live(now=1000.0)]
            ctx.check(f"still listed at first, got {got}", got == ["stepped"])
            ctx.check(f"the mark is now, got {_file_rows()['stepped'].get(registry.UNREACHABLE)}",
                      _file_rows()["stepped"].get(registry.UNREACHABLE) == 1000.0)
            ctx.check("29.9 s later: still listed",
                      [r["session_id"] for r in registry.list_live(now=1029.9)] == ["stepped"])
            ctx.check("31 s later: gone", registry.list_live(now=1031.0) == [])
            ctx.check("and gone from the file", _file_rows() == {})
        finally:
            probe.close()
            lst.close()


@test
def test_a_missing_socket_file_prunes_at_once(ctx: Ctx):
    from halo_harness.remote import registry
    with _Home():
        probe = _Probe(rest=False)
        try:
            base = Path(os.environ["BRIDGE_TEST_HOME"])
            there = base / "there.ctl"
            there.write_text("", encoding="utf-8")  # a file that refuses connects: "not answering now"
            registry.register(_entry("gone", f"unix:{base / 'gone.ctl'}"))
            registry.register(_entry("there", f"unix:{there}"))
            got = [r["session_id"] for r in registry.list_live(now=1000.0)]
            ctx.check(f"the row whose socket file is gone leaves at once, got {got}", got == ["there"])
            ctx.check("and leaves the file", set(_file_rows()) == {"there"})
        finally:
            probe.close()


@test
def test_halo_ps_and_doctor_count_a_live_session(ctx: Ctx):
    """3.6.0.4 S1 repair: `halo ps` (ps_cli._sessions) and `halo doctor` (doctor_check._live_count) call
    registry._entry_alive with a row only; when it gained a clock argument both raised inside their `except Exception`
    and showed no session. They see a live row, decide a refused one as list_live does, and write nothing."""
    from halo_harness import ps_cli
    from halo_harness.remote import doctor_check, registry
    with _Home():
        lst = _Listener()
        real_alive = registry.pid_alive
        registry.pid_alive = lambda pid: pid in (424243, 424244)  # two other live processes
        try:
            registry.register(_entry("live", lst.endpoint, pid=424243))
            home = registry.registry_path().parent.parent  # the state folder halo ps reads run/sessions.json from
            got = [r["pid"] for r in ps_cli._sessions(home)]
            ctx.check(f"halo ps lists the live session, got {got}", got == [424243])
            ctx.check(f"doctor counts it, got {doctor_check._live_count()}", doctor_check._live_count() == 1)
            refused = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            refused.bind(("127.0.0.1", 0))
            port = refused.getsockname()[1]
            refused.close()  # nothing listens there: every connect is refused
            registry.register(_entry("quiet", f"tcp:127.0.0.1:{port}", pid=424244))
            before = registry.registry_path().read_text("utf-8")
            got = sorted(r["pid"] for r in ps_cli._sessions(home))
            ctx.check(f"a refused, unmarked row is 'not answering now', as list_live says, got {got}",
                      got == [424243, 424244] and doctor_check._live_count() == 2)
            ctx.check("neither writes the file", registry.registry_path().read_text("utf-8") == before)
        finally:
            registry.pid_alive = real_alive
            lst.close()



@test
def test_a_guest_bridge_is_a_watch_only_session_row_and_its_end_takes_it_all(ctx: Ctx):
    """3.6.0.25 G: Claude Code's bridge (guest/bridge.py) lists itself as every session does, `kind: guest`,
    `parent: claude-code:<pid>`, titled "Claude Code"; its end removes the row, its `.on` and its spool."""
    with _Home():
        from halo_harness.guest.bridge import GuestBridge
        from halo_harness.remote import registry
        project = Path(tempfile.mkdtemp(prefix="guest-proj-"))
        bridge = GuestBridge(os.getpid(), project).start()
        try:
            ctx.check("the bridge opened", bridge is not None)
            rows = [r for r in registry.list_live() if r.get("kind") == "guest"]
            ctx.check(f"one guest row, got {rows}", len(rows) == 1)
            row = rows[0]
            ctx.check(f"its parent and title: {row.get('parent')}, {row.get('title')}",
                      row["parent"] == f"claude-code:{os.getpid()}" and row["title"] == "Claude Code"
                      and row["cwd"] == str(project))
            ctx.check("its .on and its spool are there", bridge.on.is_file() and bridge.spool.is_file())
            if os.name != "nt":
                ctx.check("the spool is 0600", (bridge.spool.stat().st_mode & 0o777) == 0o600)
        finally:
            if bridge is not None:
                bridge.close()
        ctx.check("its end: no row", not [r for r in registry.list_live() if r.get("kind") == "guest"])
        ctx.check("its end: no .on, no spool", not bridge.on.exists() and not bridge.spool.exists())


_FRESH_BRIDGE = r"""
import json, os, sys, tempfile
started = []
def _audit(event, args):
    if event in ("subprocess.Popen", "os.system", "os.posix_spawn", "os.spawn", "os.exec", "os.startfile", "os.fork"):
        started.append([event, str(args[1] if event == "subprocess.Popen" and len(args) > 1 else args)[:200]])
sys.addaudithook(_audit)
from halo_harness.guest.bridge import GuestBridge
bridge = GuestBridge(os.getpid(), tempfile.mkdtemp(prefix="guest-proj-")).start()
bridge.poll()
bridge.close()
print(json.dumps({"opened": bridge is not None, "started": started}))
"""


@test
def test_a_guest_bridge_starts_no_process_in_a_fresh_interpreter(ctx: Ctx):
    """The check: the bridge's way in (runtime._open -> session_identity.harness) asked platform.system(), which on
    Windows' Python 3.11 starts `cmd /c ver` the first time. A process that already asked once hides it, so the bridge
    is started in a FRESH interpreter, every process start it makes counted by an audit hook."""
    import subprocess
    with _Home():
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)}
        r = subprocess.run([sys.executable, "-c", _FRESH_BRIDGE], capture_output=True, text=True, timeout=120,
                           env=env, cwd=os.environ["BRIDGE_TEST_HOME"])
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            got = {"opened": None, "started": None, "stderr": r.stderr[-400:]}
        ctx.check(f"the bridge opened in the fresh interpreter, got {got}", got.get("opened") is True)
        ctx.check(f"and started no process, got {got.get('started')}", got.get("started") == [])


@test
def test_a_guest_spool_of_a_dead_claude_code_is_swept_at_a_bridges_start(ctx: Ctx):
    import subprocess
    with _Home():
        from halo_harness.guest import guest_dir
        from halo_harness.guest.bridge import GuestBridge
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait(60)
        dead = p.pid
        d = guest_dir()
        left = [d / f"{dead}.on", d / f"{dead}.jsonl", d / f"{dead}.17.jsonl"]
        for f in left:
            f.write_text("{}")
        other = d / "notes.txt"
        other.write_text("kept")
        bridge = GuestBridge(os.getpid(), Path(tempfile.mkdtemp(prefix="guest-proj-"))).start()
        try:
            ctx.check(f"the dead pid's files are gone: {[f.name for f in left if f.exists()]}", not any(f.exists() for f in left))
            ctx.check("another file stays", other.exists())
        finally:
            if bridge is not None:
                bridge.close()


@test
def test_a_guest_spool_is_swept_by_its_bridge_even_when_its_claude_pid_was_given_to_another_program(ctx: Ctx):
    """The check: a bridge killed hard (Windows ends Claude Code's MCP tree 300 ms after closing its input) leaves its
    `.on` and spool; Windows gives the pid to the next program at once, so a sweep keyed on Claude Code's pid kept a
    dead session's words. The `.on` names its bridge (pid and start time): a dead bridge means stale files."""
    import subprocess
    with _Home():
        from halo_harness.guest import guest_dir
        from halo_harness.guest.bridge import GuestBridge
        from halo_harness.bg_run import process_start_time as _start_mark
        from halo_harness.remote import runtime
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait(60)
        reused = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])  # the pid's next program
        bridge = None
        try:
            d = guest_dir()
            stale = [d / f"{reused.pid}.on", d / f"{reused.pid}.jsonl"]
            stale[0].write_text(json.dumps({"claude_pid": reused.pid, "bridge_pid": gone.pid, "bridge_start": "1"}))
            stale[1].write_text('{"prompt": "the dead session\'s words"}\n')
            alive = [d / f"{os.getppid()}.on", d / f"{os.getppid()}.jsonl"]  # a running bridge (this process)
            alive[0].write_text(json.dumps({"claude_pid": os.getppid(), "bridge_pid": os.getpid(),
                                            "bridge_start": _start_mark(os.getpid())}))
            alive[1].write_text("")
            bridge = GuestBridge(os.getpid(), Path(tempfile.mkdtemp(prefix="guest-proj-"))).start()
            ctx.check(f"the dead bridge's files are gone though its Claude Code's pid runs: "
                      f"{[f.name for f in stale if f.exists()]}", not any(f.exists() for f in stale))
            ctx.check("a running bridge's files stay", all(f.exists() for f in alive))
            seen, real_stop = [], runtime.stop_one
            runtime.stop_one = lambda act: (seen.append(bridge.spool.exists() or bridge.on.exists()), real_stop(act))
            try:
                bridge.close()
            finally:
                runtime.stop_one = real_stop
            ctx.check(f"its end removes the .on and the spool BEFORE the row, got {seen}", seen == [False])
        finally:
            if bridge is not None:
                bridge.close()
            reused.kill()
            reused.wait(60)


def _dead_bridge_files(d: Path, gone_pid: int) -> list:
    on, spool = d / f"{gone_pid}.on", d / f"{gone_pid}.jsonl"
    job = d / f"{gone_pid}.job.{'ab' * 16}.json"  # 3.6.0.26 H: a hand-out's record goes with its bridge's spool
    on.write_text(json.dumps({"claude_pid": gone_pid, "bridge_pid": gone_pid, "bridge_start": "1"}))
    spool.write_text('{"prompt": "the dead session\'s words"}\n')
    job.write_text('{"job": {"goal": "the dead session\'s task"}}')
    return [on, spool, job]


@test
def test_a_bridge_ended_hard_leaves_nothing_at_each_place_that_sweeps(ctx: Ctx):
    """The review: a bridge ended hard (halo update's stop on Windows, a closed console) left its `.on` and spool
    until the next bridge's start, which may never come. Each of these sweeps them: halo update right after its
    stops, `halo guest status`, `halo guest uninstall`, `halo doctor`'s row, a Studio start."""
    import subprocess
    with _Home():
        home = Path(os.environ["BRIDGE_TEST_HOME"])
        from halo_harness import update_stop
        from halo_harness.guest import guest_dir, install
        from halo_harness.studio.server import start_server
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        gone.wait(60)
        d = guest_dir()
        real = (update_stop.registered, update_stop.scanned)

        def by_update():
            update_stop.registered, update_stop.scanned = (lambda *_a, **_k: []), (lambda *_a, **_k: [])
            try:
                update_stop.stop_lingering()
            finally:
                update_stop.registered, update_stop.scanned = real

        def by_studio():
            (home / "proj").mkdir(exist_ok=True)
            (home / "st").mkdir(exist_ok=True)
            srv = start_server(port=0, cwd=home / "proj", state_dir=home / "st")
            srv.server_close()
        places = {"halo update's stops": by_update,
                  "halo guest status": lambda: install.cmd_status([]),
                  "halo guest uninstall": lambda: install.cmd_uninstall(["--to", tempfile.mkdtemp(prefix="guest-plug-")]),
                  "halo doctor's row": install.doctor_line,
                  "a Studio start": by_studio}
        for name, run in places.items():
            left = _dead_bridge_files(d, gone.pid)
            with contextlib.redirect_stdout(io.StringIO()):
                run()
            ctx.check(f"{name}: the dead bridge's .on and spool are gone, left {[f.name for f in left if f.exists()]}",
                      not any(f.exists() for f in left))


@test
def test_guest_status_prints_the_lines_a_bridge_dropped(ctx: Ctx):
    with _Home():
        from halo_harness.guest import install
        from halo_harness.guest.bridge import GuestBridge
        bridge = GuestBridge(os.getpid(), Path(tempfile.mkdtemp(prefix="guest-proj-"))).start()
        try:
            if bridge is None:
                ctx.check("this build opens a session socket", False)
                return
            bridge.handle.feed.dropped = 3
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                install.cmd_status([])
            ctx.check(f"the count is printed: {out.getvalue()!r}",
                      "lines dropped (another folder or another session): 3" in out.getvalue())
        finally:
            if bridge is not None:
                bridge.close()


@test
def test_guest_status_prints_the_setting_and_the_jobs_a_bridge_runs(ctx: Ctx):
    """3.6.0.26 H: `halo guest status` says the setting and, per bridge, the hand-out jobs that run."""
    import threading
    from types import SimpleNamespace
    with _Home():
        home = Path(os.environ["BRIDGE_TEST_HOME"])
        (home / ".halo").mkdir(parents=True, exist_ok=True)
        (home / ".halo" / "config.json").write_text(json.dumps({"guest": {"hand_out": "local"}}), encoding="utf-8")
        from halo_harness.guest import install
        from halo_harness.guest.bridge import GuestBridge
        from halo_harness.guest.hand_out import HandOuts
        bridge = GuestBridge(os.getpid(), Path(tempfile.mkdtemp(prefix="guest-proj-"))).start()
        try:
            if bridge is None:
                ctx.check("this build opens a session socket", False)
                return
            jobs = HandOuts(bridge.project, sid="g", directory=bridge.dir, claude_pid=os.getpid())
            brief = {"job_id": "c0ffee" * 5 + "00", "state": "running", "model": "ol:qwen3:30b", "minutes": 1.5}
            jobs.jobs["x"] = SimpleNamespace(done=threading.Event(), brief=lambda: brief)
            bridge.handle.hand_outs = jobs
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                install.cmd_status([])
            text = out.getvalue()
            ctx.check(f"the setting is said: {text!r}", "The setting: hand-outs: local" in text)
            ctx.check(f"and its job: {text!r}", "hand-outs: on; ol:qwen3:30b running 1.5 min (job c0ffeec0)" in text)
        finally:
            if bridge is not None:
                bridge.close()


@test
def test_studio_lists_no_hand_out_worker_as_a_session_and_attaches_none(ctx: Ctx):
    """3.6.0.26 H: a worker's own registry row (`parent: guest:<bridge session>`) is drawn as a row of its guest's
    tree: Studio's session list and its event bridge leave it out; every other row is as before."""
    from types import SimpleNamespace
    from halo_harness.remote import registry
    from halo_harness.studio import events, sessions_api
    rows = [{"session_id": "g-1", "kind": "guest", "parent": "claude-code:7", "pid": os.getpid(), "started": 1.0},
            {"session_id": "w-1", "kind": "print", "parent": "guest:guest-7-8", "pid": os.getpid(), "started": 2.0},
            {"session_id": "s-1", "kind": "headless", "parent": "studio:9", "pid": os.getpid(), "started": 3.0}]
    real = registry.list_live, sessions_api.statuses
    try:
        registry.list_live = lambda *a, **kw: [dict(r) for r in rows]
        sessions_api.statuses = lambda entries: {}
        _code, listed = sessions_api.list_sessions(SimpleNamespace(params={}, body={}))
        ctx.check(f"the list: the guest and the Studio session, never the worker; got {[r['session_id'] for r in listed]}",
                  [r["session_id"] for r in listed] == ["g-1", "s-1"])
    finally:
        registry.list_live, sessions_api.statuses = real
    attached = []
    bridge = events.EventBridge(list_live=lambda: [dict(r) for r in rows])
    bridge._attach = lambda entry: attached.append(entry["session_id"])
    bridge.scan()
    ctx.check(f"the event bridge attaches the guest and the session, not the worker; got {attached}",
              sorted(attached) == ["g-1", "s-1"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
