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
        import subprocess
        project = Path(tempfile.mkdtemp(prefix="guest-proj-"))
        started, real_popen = [], subprocess.Popen

        class _Counted(real_popen):  # the bridge starts no process (not even the git query of a project row)
            def __init__(self, *a, **kw):
                started.append(a[0] if a else kw.get("args"))
                super().__init__(*a, **kw)
        subprocess.Popen = _Counted
        try:
            bridge = GuestBridge(os.getpid(), project).start()
            bridge.poll()
        finally:
            subprocess.Popen = real_popen
        ctx.check(f"the bridge started no process, got {started}", started == [])
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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
