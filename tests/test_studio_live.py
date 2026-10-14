"""tests.test_studio_live -- Halo 3.0.3.0 round R3: Studio's live feed.

A real `ControlServer` over the remote rig's fake session is registered in a
scoped `~/.halo/run/sessions.json`; Studio (`start_server(port=0)`) streams
`/api/events?t=<token>` and the test reads it with urllib: the synthesized
`sessions` frame names the session, a `subagent_start` pushed through the
session's event hub arrives as an SSE frame within 2 s, and removing the
session publishes a detach. Also: a missing or wrong token, a foreign Host
and a foreign Origin are 403; the per-browser queue keeps the newest 512.

Run: python tests/test_studio_live.py
"""

from __future__ import annotations

import http.client
import json
import os
import queue
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.remote_rig import Rig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Studio:
    def __enter__(self):
        from halo_harness.studio.server import start_server
        state = Path(tempfile.mkdtemp(prefix="studio-live-")) / ".halo"
        state.mkdir()
        self.srv = start_server(port=0, cwd=state.parent, state_dir=state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()


class _Reader:
    """Reads SSE frames off one /api/events response into a queue."""

    def __init__(self, url: str):
        self.frames: "queue.Queue" = queue.Queue()
        self.resp = urllib.request.urlopen(url, timeout=10)
        self.headers = dict(self.resp.headers)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        kind = ""
        try:
            for raw in self.resp:
                line = raw.decode("utf-8").rstrip("\r\n")
                if line.startswith("event: "):
                    kind = line[7:]
                elif line.startswith("data: "):
                    self.frames.put((kind, json.loads(line[6:])))
        except Exception:
            pass

    def wait(self, pred, timeout: float):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                kind, frame = self.frames.get(timeout=max(0.01, end - time.monotonic()))
            except queue.Empty:
                break
            if pred(kind, frame):
                return frame
        return None

    def close(self):
        """Shut the socket down and let the reader thread see EOF (on Windows
        resp.close() would wait out the reader's 10 s recv timeout)."""
        try:
            import socket
            self.resp.fp.raw._sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass


def _register(rig):
    from halo_harness.remote import registry
    sid = rig.server.session_id
    registry.register(registry.make_entry(session_id=sid, cwd=str(rig.cwd), endpoint=rig.server.endpoint,
                                          token=rig.server.token, title="live test", mode="default"))
    return sid


@test
def test_a_pushed_event_reaches_the_browser_within_two_seconds(ctx: Ctx):
    from halo_harness import events
    with Rig() as rig, _Studio() as s:
        sid = _register(rig)
        rd = _Reader(f"{s.base}/api/events?t={s.srv.token}&sessions=all")
        try:
            ctx.check(f"SSE headers, got {rd.headers}", rd.headers.get("Content-Type", "").startswith("text/event-stream")
                      and rd.headers.get("Cache-Control") == "no-store" and rd.headers.get("X-Accel-Buffering") == "no")
            first = rd.wait(lambda k, f: k == "sessions", 3)
            ctx.check("the first frame is the sessions snapshot", first is not None and first["event"] == "sessions")
            att = rd.wait(lambda k, f: k == "sessions" and f["data"].get("attached") == sid, 6)
            ctx.check("the bridge attaches the registered session", att is not None)
            if att:
                row = att["data"]["sessions"][0]
                ctx.check(f"the sessions frame carries public fields only, got {sorted(row)}",
                          row.get("title") == "live test" and "token" not in row and "endpoint" not in row)
            t0 = time.monotonic()
            rig.handle.hub.publish(events.Event("subagent_start", {"description": "probe"}, turn=3, agent_id="ag-1"))
            got = rd.wait(lambda k, f: k == "subagent_start", 2.0)
            ctx.check(f"subagent_start arrived within 2 s ({time.monotonic() - t0:.2f} s)", got is not None)
            if got:
                ctx.check(f"the frame is {{session_id, event, data, turn, agent_id, ts}}, got {got}",
                          got["session_id"] == sid and got["data"] == {"description": "probe"} and got["turn"] == 3
                          and got["agent_id"] == "ag-1" and isinstance(got["ts"], (int, float)))
            from halo_harness.remote import registry
            registry.unregister(sid)
            det = rd.wait(lambda k, f: k == "sessions" and f["data"].get("detached") == sid, 6)
            ctx.check("removing the session publishes a detach", det is not None and det["data"]["sessions"] == [])
        finally:
            rd.close()


@test
def test_one_session_filter_keeps_other_sessions_out(ctx: Ctx):
    from halo_harness.studio.events import BrowserQueue
    q = BrowserQueue("abc", maxlen=3)
    ctx.check("its own session passes", q.wants({"event": "status", "session_id": "abc"}))
    ctx.check("another session is filtered out", not q.wants({"event": "status", "session_id": "zzz"}))
    ctx.check("sessions frames always pass", q.wants({"event": "sessions", "session_id": None}))
    for i in range(5):
        q.put({"i": i})
    ctx.check("a full queue drops the oldest", [q.get(0.01)["i"] for _ in range(3)] == [2, 3, 4] and q.dropped == 2)
    from halo_harness.studio import events as ev
    ctx.check("the browser queue holds 512 frames", ev.QUEUE_MAX == 512 and BrowserQueue().get.__name__ == "get")


@test
def test_wrong_token_foreign_host_and_origin_are_403(ctx: Ctx):
    with _Studio() as s:
        def status(path, headers=None):
            conn = http.client.HTTPConnection("127.0.0.1", s.port, timeout=5)
            conn.request("GET", path, headers=headers or {})
            r = conn.getresponse()
            code = r.status
            conn.close()
            return code
        ctx.check("no token is a 403", status("/api/events") == 403)
        ctx.check("a wrong token is a 403", status("/api/events?t=nope") == 403)
        ctx.check("a bearer header does not stand in for ?t=", status("/api/events", {"Authorization": "Bearer " + s.srv.token}) == 403)
        ctx.check("a foreign Host is a 403", status(f"/api/events?t={s.srv.token}", {"Host": f"evil.example:{s.port}"}) == 403)
        ctx.check("a foreign Origin is a 403", status(f"/api/events?t={s.srv.token}", {"Origin": "http://evil.example"}) == 403)
    ctx.check("no bridge thread was started by the 403 requests", s.srv.events is None)


@test
def test_server_close_ends_open_streams(ctx: Ctx):
    with _Studio() as s:
        rd = _Reader(f"{s.base}/api/events?t={s.srv.token}")
        ctx.check("the stream opened", rd.wait(lambda k, f: k == "sessions", 3) is not None)
        bridge = s.srv.events
    ctx.check("server_close closed the bridge", bridge is not None and bridge.closed)
    rd.close()


if __name__ == "__main__":
    os.environ.setdefault("BRIDGE_TEST_NO_BACKGROUND_NET", "1")
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio live feed tests"))
