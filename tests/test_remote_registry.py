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
            ctx.check("endpoint_for before the sweep", registry.endpoint_for("deadsock") is None)  # sweeps
            ids = {r["session_id"] for r in json.loads(registry.registry_path().read_text("utf-8"))["sessions"]}
            ctx.check("dead pid + refused endpoint removed from the file, live kept", ids == {"alive"})
            ctx.check("list_live returns only the live one", [r["session_id"] for r in registry.list_live()] == ["alive"])
            ctx.check("endpoint_for finds the live one", registry.endpoint_for("alive") == live.endpoint)
        finally:
            registry.pid_alive = real
            live.close()
            dead_pid_listener.close()


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


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
