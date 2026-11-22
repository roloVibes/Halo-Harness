"""tests.test_headless_session -- Halo 3.3.11.0 R2, a session with no terminal (`halo --headless --session-for
studio`, halo_harness/headless_session.py): a real child under a scratch home over the fake upstream
(tests/helpers/headless_rig.py); no model call, every child ended by the teardown and checked gone.

1. its registry row says `kind: headless` and `parent: studio:<pid>`; its status says the same;
2. a `submit` through the socket runs a turn; the reply is in its tail and in the session log on disk;
3. an ask parks: the Write call waits on a permission card, the status lists it under `parked`; an `answer`
   through the socket releases it and the turn ends;
4. `shutdown` ends the child (exit 0) and its registry row goes;
5. the TUI's builder (`tui/bootstrap.build_controller`, what `halo --resume <id>` runs) opens its log;
6. `/quit` through the handle ends it (in-process, the scripted session) and the slash never reaches the registry.
Run: python -m tests.test_headless_session
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_session_with_no_terminal_end_to_end(ctx: Ctx):
    from tests.helpers.session_rig import wait_for
    from tests.helpers.headless_rig import ASK_TEXT, MODEL, REPLY, HeadlessRig
    with HeadlessRig() as rig:
        proc = rig.start()
        entry = rig.entry()
        ctx.check(f"the child registered, got {entry!r}\n{rig.child_log()}", entry is not None)
        if entry is None:
            return
        ctx.check(f"kind headless, parent studio:<pid>, got {entry.get('kind')} {entry.get('parent')}",
                  entry.get("kind") == "headless" and str(entry.get("parent") or "").startswith("studio:")
                  and str(entry.get("parent")).split(":", 1)[1].isdigit())
        sid = entry["session_id"]
        c = rig.client(entry)
        st = c.call("status")["result"]
        ctx.check(f"the status says headless, takes turns, nothing parked, got {st.get('kind')} {st.get('parked')}",
                  st.get("kind") == "headless" and st.get("accepts_turns") is True and st.get("parked") == [])
        c.call("subscribe")
        r = c.call("submit", text="hello from nowhere", when_busy="refuse")
        ctx.check(f"submit took the turn, got {r!r}", r.get("ok") is True)
        done = c.wait_event("turn_done", 40)
        ctx.check("the turn ran to its end", done is not None)
        ctx.check("the reply is in the tail", REPLY in c.call("tail", n=4)["result"]["markdown"])
        log = wait_for(lambda: REPLY in rig.log_text(sid) and rig.log_text(sid), 10)
        ctx.check("the session log on disk holds the turn", bool(log) and "hello from nowhere" in log)

        rig.idle(c)
        c.call("submit", text=f"{ASK_TEXT} for a folder", when_busy="refuse")
        ask = c.wait_event("permission_request", 40)
        ctx.check(f"the Write call asks, got {ask!r}", ask is not None and ask["data"].get("name") == "Write")
        rid = (ask or {}).get("data", {}).get("id")
        parked = wait_for(lambda: c.call("status")["result"].get("parked"), 10) or []
        ctx.check(f"the ask is parked in the status, got {parked}",
                  len(parked) == 1 and parked[0]["id"] == rid and parked[0]["kind"] == "permission"
                  and isinstance(parked[0]["since"], float))
        ctx.check("the status says waiting on it", rid in (c.call("status")["result"]["pending"]["permission"] or []))
        a = c.call("answer", kind="permission", request_id=rid, action="allow")
        ctx.check(f"the answer through the socket released it, got {a!r}", a.get("ok") is True)
        ctx.check("the turn ended after the tool ran", c.wait_event("turn_done", 40) is not None)
        ctx.check("the tool ran in the project", wait_for(lambda: (rig.proj / "headless-made.txt").is_file(), 10) is True)
        ctx.check("nothing parked after the answer", wait_for(lambda: c.call("status")["result"].get("parked") == [], 10) is True)

        rig.idle(c)
        s = c.call("shutdown", by="test", via="test", reason="the end")
        ctx.check(f"shutdown taken, got {s!r}", s.get("ok") is True)
        try:
            code = proc.wait(40)
        except Exception:
            code = None
        ctx.check(f"the child ended with 0, got {code}\n{rig.child_log()}", code == 0)
        ctx.check("its registry row is gone", wait_for(lambda: not any(x.get("session_id") == sid for x in rig.rows()), 10) is True)

        saved = {k: os.environ.get(k) for k in ("BRIDGE_OPENROUTER_BASE_URL", "OPENROUTER_API_KEY")}
        os.environ.update(BRIDGE_OPENROUTER_BASE_URL=rig.mock.base_url, OPENROUTER_API_KEY="test-key")
        try:
            from halo_harness.tui.bootstrap import build_controller
            controller, _r, _f = build_controller(SimpleNamespace(cwd=str(rig.proj), resume=sid, model=MODEL))
            users = [b.get("text") for n in controller.session.log.nodes() if n.get("type") == "user"
                     for b in n.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
            ctx.check(f"--resume <id> opens its log, got {controller.session.log.session_id} {users[:2]}",
                      controller.session.log.session_id == sid and "hello from nowhere" in users)
            for fn in (lambda: controller.mcp_manager and controller.mcp_manager.close_all(), controller.session.close_runtimes):
                try:
                    fn()
                except Exception:
                    pass
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
    ctx.check(f"no headless child survives, got {rig.survivors()}", rig.survivors() == [])


@test
def test_a_bang_line_runs_in_a_session_with_no_terminal(ctx: Ctx):
    """3.6.0.12 BS, a real `halo --headless` child (Studio's own New session): a `!` line over the `slash` door runs
    with no turn; an asking `!` parks as a `permission_request` an answer runs; closing the session ends a `!`
    command still running, and its process with it."""
    from halo_harness.bg_run import pid_alive
    from tests.helpers.session_rig import wait_for
    from tests.helpers.headless_rig import HeadlessRig
    pid = 0
    import json
    with HeadlessRig() as rig:
        try:
            settings = rig.home / ".claude" / "settings.json"  # `touch` asks in this home, whatever its allow rules
            data = json.loads(settings.read_text("utf-8"))
            data.setdefault("permissions", {}).setdefault("ask", []).append("Bash(touch:*)")
            settings.write_text(json.dumps(data, indent=2), "utf-8")
            proc = rig.start()
            entry = rig.entry()
            ctx.check(f"the child registered\n{rig.child_log()}", entry is not None)
            if entry is None:
                return
            c = rig.client(entry)
            c.call("subscribe")
            r = (c.call("slash", line="!echo bang-with-no-terminal").get("result") or {})
            ctx.check(f"`!echo` ran with its output, got {r}", r.get("state") == "ran" and "bang-with-no-terminal" in str(r.get("output")))
            ctx.check("its rows are on the feed", c.wait_event("tool_result", 20) is not None)
            ctx.check("no turn ran", c.call("status")["result"].get("turn", 0) == 0)
            r = (c.call("slash", line="!touch bang-asked.txt").get("result") or {})
            ctx.check(f"a command the mode asks about asks, got {r} in {c.call('status')['result'].get('permission_mode')}",
                      r.get("state") == "asked")
            ask = c.wait_event("permission_request", 20)
            ctx.check(f"its ask is on the feed, got {ask}", ask is not None and ask["data"].get("id") == r.get("id"))
            ctx.check("nothing ran yet", not (rig.proj / "bang-asked.txt").exists())
            a = c.call("answer", kind="permission", request_id=r.get("id"), action="allow")
            ctx.check(f"the answer was taken, got {a}", a.get("ok") is True)
            ctx.check("the command ran after the allow", wait_for(lambda: (rig.proj / "bang-asked.txt").exists(), 20) is True)
            pid_file = rig.proj / "bang-child.pid"
            script = f"import os, time; open({pid_file.as_posix()!r}, 'w').write(str(os.getpid())); time.sleep(60)"
            r = (c.call("slash", line=f"!'{Path(sys.executable).as_posix()}' -c \"{script}\"").get("result") or {})
            if r.get("state") == "asked":  # the mode's verdict on this one is the engine's, not this test's
                c.call("answer", kind="permission", request_id=r.get("id"), action="allow")
            ctx.check(f"a long command runs, got {r}", r.get("state") in ("running", "asked")
                      and wait_for(lambda: pid_file.is_file() and pid_file.read_text().strip(), 30) is not None)
            pid = int((pid_file.read_text() if pid_file.is_file() else "0").strip() or 0)
            ctx.check(f"its process lives, pid {pid}", pid > 0 and pid_alive(pid))
            c.call("shutdown", by="test", via="test", reason="the end")
            try:
                code = proc.wait(40)
            except Exception:
                code = None
            ctx.check(f"the session closed, got {code}\n{rig.child_log()}", code == 0)
            ctx.check("closing ended the running `!` command's process", wait_for(lambda: not pid_alive(pid), 15) is True)
        finally:
            if pid and pid_alive(pid):  # a red run: end the process this test started, by its pid
                import signal
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
    ctx.check(f"no headless child survives, got {rig.survivors()}", rig.survivors() == [])


@test
def test_quit_through_the_handle_ends_it(ctx: Ctx):
    from tests.helpers.remote_rig import Rig
    from halo_harness.headless_session import HeadlessHandle
    with Rig(serve=False) as rig:
        done = threading.Event()
        h = HeadlessHandle(rig.controller, done)
        ctx.check("kind is headless", h.kind == "headless")
        out = h.run_slash("quit")
        ctx.check(f"/quit ends it, got {out!r}", done.is_set() and "Ending this session" in out)
        done.clear()
        ctx.check("/exit too", "Ending" in h.run_slash("/exit") and done.is_set())
        ctx.check("another slash runs as in the TUI", h.run_slash("cost", "x") == "ran /cost x")
        h._close_after_shutdown("shut down")
        ctx.check("shutdown sets the same end", done.is_set())


@test
def test_shutdown_answers_before_the_session_closes_its_socket(ctx: Ctx):
    """3.6.0.4 S3-1: `shutdown` started the session's end (control_shutdown -> its thread -> the end hook -> the
    socket closed) BEFORE its own answer was written, so a reply thread that ran late under load wrote into a
    closed socket and the caller read 'control socket closed' for a shutdown that worked. The order is injected:
    the reply's send waits up to 3 s for the session's end to begin (the real end closes the server, as the
    headless session's quit does). Fixed, the end begins only after the answer went out, and still within 10 s.
    S4-1: a send held past SHUTDOWN_REPLY_BOUND_S (2 s) gives way to the end by design, so this test, whose injected
    lateness is 3 s, raises the bound to 30 s for its own run: it proves the order, the bound has its own test."""
    from tests.helpers.remote_rig import Rig
    from halo_harness.remote import control_socket
    ending = threading.Event()
    real_send = control_socket._Conn.send
    saved_bound = getattr(control_socket, "SHUTDOWN_REPLY_BOUND_S", None)
    control_socket.SHUTDOWN_REPLY_BOUND_S = 30.0

    def late_send(self, obj):
        if isinstance(obj, dict) and isinstance(obj.get("result"), dict) and "shutdown" in obj["result"]:
            ending.wait(3.0)
        return real_send(self, obj)

    control_socket._Conn.send = late_send
    try:
        with Rig() as rig:
            server = rig.server
            rig.controller.on_control_shutdown = lambda _t: (server.close(), ending.set())
            c = rig.client()
            c.call("subscribe")
            try:
                s = c.call("shutdown", by="test", via="test", reason="the end")
            except ConnectionError as e:
                s = {"error": f"{type(e).__name__}: {e}"}
            ctx.check(f"the caller reads the answer, got {s!r}", s.get("ok") is True and s["result"] == {"shutdown": True})
            ctx.check("the session's end still begins, within 10 s", ending.wait(10.0))
            closed = server.closed.wait(10.0)
            ctx.check("its socket closed after the answer", closed)
    finally:
        control_socket._Conn.send = real_send
        if saved_bound is not None:
            control_socket.SHUTDOWN_REPLY_BOUND_S = saved_bound


def _halo_threads(before: set) -> list:
    return [t.name for t in threading.enumerate() if t not in before and t.is_alive() and t.name.startswith("halo-ctl")]


@test
def test_a_subscriber_that_stopped_reading_cannot_hold_off_shutdown(ctx: Ctx):
    """3.6.0.4 S4-1: a caller that subscribed on a connection and stopped reading fills its socket's buffers; the
    feed thread then waits in its send holding the connection's send lock, so the answer to `shutdown` on that
    connection waits too. The end began only after the answer, so it never began. Fixed: it begins when the answer
    is out OR after SHUTDOWN_REPLY_BOUND_S (2 s), whichever comes first; the timer is gone afterwards and so is every
    connection thread. Small buffers on both ends make a few megabytes fill them; fewer than 256 frames are queued,
    so the subscriber is never dropped (a drop would close the socket and hide the fault)."""
    import json
    import socket
    from tests.helpers.remote_rig import Rig
    from tests.helpers.session_rig import wait_for
    from halo_harness import events
    from halo_harness.remote import control_socket
    before = set(threading.enumerate())
    ending = threading.Event()
    with Rig(sndbuf=2048) as rig:
        server = rig.server
        rig.controller.on_control_shutdown = lambda _t: (server.close(), ending.set())
        c = rig.client()
        c.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2048)
        c.call("subscribe")  # ... and never reads again
        conn = wait_for(lambda: next((x for x in server._conns if x._sub is not None), None), 10)
        blob = "x" * 65536
        for i in range(120):
            rig.controller.events.put(events.Event("notification", {"text": blob, "level": "info", "i": i}))
        stuck = wait_for(lambda: conn._send_lock.locked() and conn._sub is not None and conn._sub._q.qsize() >= 2, 20)
        ctx.check("the feed waits in its send (the caller stopped reading) and was not dropped", stuck is True)
        line = {"id": 7, "cmd": "shutdown", "by": "test", "via": "test", "reason": "the end"}
        c.sock.sendall((json.dumps(line) + "\n").encode("utf-8"))
        bound = getattr(control_socket, "SHUTDOWN_REPLY_BOUND_S", 2.0)
        ctx.check(f"the session's end begins within the bound ({bound} s) plus 8 s", ending.wait(bound + 8.0))
        ctx.check("its socket closed", server.closed.wait(10.0))
    left = wait_for(lambda: not _halo_threads(before), 10)
    ctx.check(f"no timer and no connection thread is left, got {_halo_threads(before)}", left is True)


@test
def test_a_caller_that_closed_still_ends_the_session_without_the_bound(ctx: Ctx):
    """3.6.0.4 S4-1: a caller that sends `shutdown` and closes at once: the answer's send returns (written or
    failed) and the end begins then, not from the bound's timer (the bound is raised to 60 s here to prove it)."""
    import json
    from tests.helpers.remote_rig import Rig
    from tests.helpers.session_rig import wait_for
    from halo_harness.remote import control_socket
    before = set(threading.enumerate())
    saved = getattr(control_socket, "SHUTDOWN_REPLY_BOUND_S", None)
    control_socket.SHUTDOWN_REPLY_BOUND_S = 60.0
    ending = threading.Event()
    try:
        with Rig() as rig:
            server = rig.server
            rig.controller.on_control_shutdown = lambda _t: (server.close(), ending.set())
            c = rig.client()
            c.call("ping")
            line = {"id": 7, "cmd": "shutdown", "by": "test", "via": "test", "reason": "the end"}
            c.sock.sendall((json.dumps(line) + "\n").encode("utf-8"))
            c.close()
            ctx.check("the session's end begins well inside the 60 s bound", ending.wait(10.0))
        left = wait_for(lambda: not _halo_threads(before), 10)
        ctx.check(f"no timer and no connection thread is left, got {_halo_threads(before)}", left is True)
    finally:
        if saved is None:
            del control_socket.SHUTDOWN_REPLY_BOUND_S
        else:
            control_socket.SHUTDOWN_REPLY_BOUND_S = saved


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
