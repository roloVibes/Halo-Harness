"""tests.test_remote_control_socket -- Halo 2.0.9 round 2: the per-session
control socket (wire, token, feed, tee, slow subscriber, shutdown).

A real `Controller` + real `ControllerHandle` + real `ControlServer` over a
scripted `FakeSession`; a fake client talks the wire. The Windows loopback
half (token handshake) runs on Windows; the Unix-socket half (file modes)
runs on POSIX and is a SKIP on a platform without AF_UNIX.
"""
from __future__ import annotations

import os
import queue
import socket
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.remote_rig import Rig
from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all

test, TESTS = new_registry()


def _drain_kinds(q) -> list:
    out = []
    while True:
        try:
            item = q.get_nowait()
        except queue.Empty:
            return out
        if item is not None:
            out.append(item.kind)


@test
def test_every_cmd_round_trips(ctx: Ctx):
    from halo_harness.remote.protocol import CMDS
    ctx.check("cmd set is the brief's thirteen plus round 4's `note`, 3.0.5.0's agent commands and 3.3.11.0's `receipts`",
              set(CMDS) == {"status", "submit", "steer", "interrupt", "answer", "model", "effort", "mode",
                            "slash", "tail", "subscribe", "unsubscribe", "ping", "note", "agents", "agent_tail",
                            "agent_steer", "agent_stop", "pause", "resume", "shutdown", "agent_follow", "receipts"})
    with Rig() as rig:
        c = rig.client()
        r = c.call("ping")
        ctx.check("ping ok", r["ok"] and r["result"]["pong"] and r["result"]["session_id"] == rig.session.log.session_id)
        r = c.call("status")["result"]
        ctx.check("status has mode/model/busy/pending", r["permission_mode"] == "default" and r["model"] == "mock/fake"
                  and r["busy"] is False and set(r["pending"]) == {"permission", "question", "plan", "approval"})
        r = c.call("submit", text="hello there")
        ctx.check("submit ok, not a steer while idle", r["ok"] and r["result"]["steered"] is False)
        ctx.check("the turn ran", rig.wait_idle())
        ctx.check("empty submit is an error", c.call("submit", text="  ")["ok"] is False)
        ctx.check("tail renders Markdown", "## User" in c.call("tail", n=5)["result"]["markdown"]
                  and "reply to: hello there" in c.call("tail", n=5)["result"]["markdown"])
        rig.session._busy.set()
        r = c.call("steer", text="actually, stop")
        rig.session._busy.clear()
        ctx.check("steer (alias of submit) while busy goes to Session.steer",
                  r["ok"] and r["result"]["steered"] is True and rig.session.steered == ["actually, stop"])
        ctx.check("interrupt sets abort", c.call("interrupt")["ok"] and rig.session.abort.is_set())
        r = c.call("mode", mode="plan")
        ctx.check("mode applied", r["ok"] and rig.session.permission_engine.mode == "plan")
        ctx.check("bad mode is an error", c.call("mode", mode="nonsense")["ok"] is False)
        r = c.call("model", ref="or:some/model")
        ctx.check("model resolved and queued", r["ok"] and rig.models == ["or:some/model"])
        r = c.call("model", ref="bad-ref")
        ctx.check("unresolvable model is ok:false with the resolver's text", not r["ok"] and "no such model" in r["error"])
        r = c.call("effort", level="high")
        ctx.check("effort goes through /effort", r["ok"] and "ran /effort high" in r["result"]["message"])
        ctx.check("bad effort is an error", c.call("effort", level="enormous")["ok"] is False)
        r = c.call("slash", name="cost", args="--all")
        ctx.check("slash name+args", r["ok"] and r["result"]["output"] == "ran /cost --all")
        ctx.check("slash line form", c.call("slash", line="/help me")["result"]["output"] == "ran /help me")
        ctx.check("unknown slash reported", "Unknown command" in c.call("slash", name="boom")["result"]["output"])
        ctx.check("subscribe ok", c.call("subscribe")["result"]["subscribed"] is True)
        ctx.check("unsubscribe ok", c.call("unsubscribe")["result"]["subscribed"] is False)
        for kind in ("permission", "question", "plan", "approval"):
            r = c.call("answer", kind=kind, request_id="nope", action="allow" if kind == "permission" else "accept")
            ctx.check(f"answer {kind} with nothing pending is ok:false", not r["ok"] and "no pending" in r["error"])
        ctx.check("unknown cmd is ok:false", c.call("explode")["ok"] is False)
        ctx.check("a non-object request is rejected, connection survives", c.call("ping")["ok"])


@test
def test_remote_commands_are_tagged_notes_not_user_bubbles(ctx: Ctx):
    with Rig() as rig:
        c = rig.client()
        c.call("submit", text="tag me")
        rig.wait_idle()
        c.call("mode", mode="auto")
        kinds_notes = []
        while True:
            try:
                ev = rig.controller.events.get_nowait()
            except queue.Empty:
                break
            if ev is not None and ev.kind == "system_note":
                kinds_notes.append(ev.data["text"])
        ctx.check("a (remote) system_note was queued for the TUI", any(t.startswith("(remote) prompt: tag me") for t in kinds_notes))
        ctx.check("mode change tagged too", any(t.startswith("(remote) mode auto") for t in kinds_notes))


@test
def test_windows_token_required_and_bad_token_dropped(ctx: Ctx):
    if os.name != "nt":
        raise SkipTest("token handshake is the Windows loopback half")
    from halo_harness.remote.client import ControlClient, parse_endpoint
    with Rig() as rig:
        kind, host, port = parse_endpoint(rig.server.endpoint)
        ctx.check("endpoint is loopback tcp", kind == "tcp" and host == "127.0.0.1")
        ctx.check("the listener is bound to loopback only", rig.server._sock.getsockname()[0] == "127.0.0.1")
        ctx.check("token is 32 hex chars", len(rig.server.token) == 32 and int(rig.server.token, 16) >= 0)
        good = rig.client()
        ctx.check("right token works", good.call("ping")["ok"])
        bad = ControlClient(rig.server.endpoint, "0" * 32)
        rig.clients.append(bad)
        try:
            first = bad.call("ping")
        except (ConnectionError, TimeoutError, OSError):
            first = {"ok": False}
        ctx.check("wrong token never gets a ping answer", first.get("ok") is not True)
        try:
            bad.call("ping")
            dropped = False
        except (ConnectionError, TimeoutError, OSError):
            dropped = True
        ctx.check("wrong-token connection is closed", dropped)
        none = ControlClient(rig.server.endpoint, None)  # no token line at all: the first request is the 'hello'
        rig.clients.append(none)
        try:
            r = none.call("ping")
        except (ConnectionError, TimeoutError, OSError):
            r = {"ok": False}
        ctx.check("a client that skips the token is dropped", r.get("ok") is not True)
        ctx.check("the server still serves the good client", good.call("ping")["ok"])
        raw = socket.create_connection((host, port), timeout=2)
        t0 = time.monotonic()
        raw.settimeout(8)
        data = raw.recv(10)
        ctx.check("silence past the 5 s handshake window closes the connection",
                  data == b"" and 4.0 <= time.monotonic() - t0 <= 7.5)
        raw.close()


@test
def test_posix_socket_file_modes(ctx: Ctx):
    if os.name == "nt" or not hasattr(socket, "AF_UNIX"):
        raise SkipTest("Unix-socket half: needs AF_UNIX")
    with Rig() as rig:
        path = rig.server.socket_path
        ctx.check("socket is <session>.ctl under run/", path.name == f"{rig.session.log.session_id}.ctl"
                  and path.parent.name == "run")
        ctx.check("socket mode 0600", (path.stat().st_mode & 0o777) == 0o600)
        ctx.check("run dir mode 0700", (path.parent.stat().st_mode & 0o777) == 0o700)
        ctx.check("no token on POSIX", rig.server.token is None)
        ctx.check("ping over the Unix socket", rig.client().call("ping")["ok"])
        server = rig.server
    ctx.check("socket file removed on close", not path.exists())
    del server


def _deep_home() -> Path:
    """A home far past the 104 bytes macOS allows a socket path (and Linux's 108), as a deep home or project is."""
    deep = Path(tempfile.mkdtemp(prefix="remote-deep-")) / ("d" * 50) / ("e" * 50) / ("f" * 50)
    deep.mkdir(parents=True)
    return deep


@test
def test_a_deep_home_still_opens_its_control_socket(ctx: Ctx):
    """3.6.0.0 R12: on an Apple silicon Mac a session under /var/folders/.../T/... got no control socket (AF_UNIX path
    too long) and some sixty tests failed behind it. Every platform: a deep home still gives a session its socket."""
    from halo_harness.remote import registry
    with Rig(home=_deep_home()) as rig:
        ctx.check("the socket opened", bool(rig.server.endpoint))
        ctx.check("ping over it", rig.client().call("ping")["ok"])
        if os.name == "nt":
            return
        from halo_harness.remote.control_socket import path_fits, pointer_target
        named, bound = rig.server.socket_path, rig.server.bind_path
        ctx.check("run/<id>.ctl is the long name", named.name == f"{rig.session.log.session_id}.ctl"
                  and named.parent.name == "run" and not path_fits(named))
        ctx.check(f"the socket itself sits at a short path, got {bound}", path_fits(bound) and bound != named)
        ctx.check("the long name is a pointer to it", pointer_target(named) == bound)
        ctx.check("the endpoint is the short socket", rig.server.endpoint == f"unix:{bound}")
        ctx.check("socket and pointer are 0600", (bound.stat().st_mode & 0o777) == 0o600
                  and (named.stat().st_mode & 0o777) == 0o600)
        ctx.check("its folder is private", (bound.parent.stat().st_mode & 0o777) == 0o700)
        registry.sweep_stale_ctl(named.parent, now=time.time() + 3600)
        ctx.check("a sweep keeps a live session's pointer and socket", named.exists() and bound.exists())
    ctx.check("both removed on close", not named.exists() and not bound.exists())


@test
def test_a_crashed_deep_sessions_pointer_and_socket_are_swept(ctx: Ctx):
    if os.name == "nt" or not hasattr(socket, "AF_UNIX"):
        raise SkipTest("Unix-socket half: needs AF_UNIX")
    from halo_harness.remote import registry
    from halo_harness.remote.control_socket import short_dir
    deep = _deep_home() / "run"
    deep.mkdir()
    dead = short_dir() / f"r12-dead-{os.getpid()}.ctl"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(str(dead))
    s.close()  # bound, never listening: what a crashed session leaves
    pointer = deep / "crashed.ctl"
    pointer.write_text(str(dead) + "\n", encoding="utf-8")
    registry.sweep_stale_ctl(deep, now=time.time() + 3600)
    ctx.check("the pointer and the socket it names are both gone", not pointer.exists() and not dead.exists())


@test
def test_a_socket_path_that_cannot_fit_is_one_plain_line(ctx: Ctx):
    if os.name == "nt" or not hasattr(socket, "AF_UNIX"):
        raise SkipTest("Unix-socket half: needs AF_UNIX")
    from halo_harness.remote import control_socket, runtime
    deep = _deep_home()
    saved = control_socket.short_dir
    control_socket.short_dir = lambda: deep  # a "short" folder that is not short
    try:
        with Rig(home=_deep_home(), serve=False) as rig:
            try:
                control_socket.ControlServer(rig.handle).start()
                err = None
            except control_socket.ControlSocketError as e:
                err = str(e)
            ctx.check(f"start raises one plain line, got {err!r}", bool(err) and "\n" not in err and "bytes" in err)
            act = runtime._open(rig.handle, rig.controller)
            ctx.check(f"the opener returns None with the same line, not a traceback, got {runtime.last_error()!r}",
                      act is None and runtime.last_error() == err)
    finally:
        control_socket.short_dir = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
