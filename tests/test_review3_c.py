"""tests.test_review3_c -- pins for the 3.0.2.0 review fix pass, round
C-studio-tools, part 1: the Studio server and its artboard route.

  * item 34   a Host header that is not the server's own loopback address and
              port is refused on the API and the page
  * item 109  a refused request closes its connection (no bogus 400 next)

3.3.13.0 R2: the artboard route's pins (items 34's files, 35, 112) are the design pack's
(halo_harness/templates/packs/design/tests/test_review_pins.py).
  * item 113  `halo studio --stop` never kills an unrelated process
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class _Studio:
    def __enter__(self):
        import tempfile
        from halo_harness.studio.server import start_server
        self.state = Path(tempfile.mkdtemp(prefix="halo-r3c-")) / "home"  # its own home: nothing leaks into the shared test home
        self.state.mkdir()
        self.srv = start_server(port=0, cwd=self.state.parent / "proj", state_dir=self.state)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]
        return self

    def __exit__(self, *a):
        self.srv.shutdown()
        self.srv.server_close()

    def get(self, path, host=None, token=True, method="GET"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.putrequest(method, path, skip_host=True)
        conn.putheader("Host", host if host is not None else f"127.0.0.1:{self.port}")
        if token:
            conn.putheader("Authorization", "Bearer " + self.srv.token)
        conn.endheaders()
        r = conn.getresponse()
        out = (r.status, dict(r.getheaders()), r.read())
        conn.close()
        return out


@test
def test_item34_foreign_host_header_is_refused_everywhere(ctx: Ctx):
    with _Studio() as s:
        for label, path in (("page", "/"), ("api", "/api/state")):
            own = s.get(path)[0]
            ctx.check(f"{label}: the own Host answers, got {own}", own == 200)
            ctx.check(f"{label}: localhost on the own port answers", s.get(path, host=f"localhost:{s.port}")[0] == 200)
            ctx.check(f"{label}: a rebound name is a 403", s.get(path, host=f"evil.example:{s.port}")[0] == 403)
            ctx.check(f"{label}: a rebound name with no port is a 403", s.get(path, host="evil.example")[0] == 403)
            ctx.check(f"{label}: loopback on another port is a 403", s.get(path, host=f"127.0.0.1:{s.port + 1}")[0] == 403)
            ctx.check(f"{label}: a missing port is a 403", s.get(path, host="127.0.0.1")[0] == 403)
        ctx.check("the API refuses a foreign Host before the token is checked", s.get("/api/state", host="evil.example:1", token=False)[0] == 403)


@test
def test_item109_a_refused_request_closes_the_connection(ctx: Ctx):
    with _Studio() as s:
        body = b'{"raw": {}}'
        head = (f"POST /api/validate HTTP/1.1\r\nHost: 127.0.0.1:{s.port}\r\nAuthorization: Bearer wrong\r\n"
                f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n").encode()
        nxt = f"GET /api/state HTTP/1.1\r\nHost: 127.0.0.1:{s.port}\r\n\r\n".encode()
        sock = socket.create_connection(("127.0.0.1", s.port), timeout=10)
        sock.sendall(head + body + nxt)
        data = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
        sock.close()
        text = data.decode("latin-1")
        ctx.check("the refusal is a 401", text.startswith("HTTP/1.1 401"))
        ctx.check("it says Connection: close", "connection: close" in text.lower())
        ctx.check("the unread body is never answered as a request line", "Bad request" not in text and text.count("HTTP/1.1 ") == 1)


def _sleeper():
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])


@test
def test_item113_stop_never_kills_an_unrelated_process(ctx: Ctx):
    import tempfile
    from halo_harness.studio.launch import stop
    from halo_harness.studio.server import studio_info_path
    state = Path(tempfile.mkdtemp(prefix="halo-r3c-"))
    victim = _sleeper()
    try:
        studio_info_path(state).write_text(json.dumps({"pid": victim.pid, "port": 1, "token": "stale"}), encoding="utf-8")
        ok, note = stop(state)
        ctx.check(f"a stale file is reported, not a stop, got {ok} {note!r}", ok is False and "stale" in note and str(victim.pid) in note)
        ctx.check("the unrelated process is still running", victim.poll() is None)
        ctx.check("studio.json is cleared", not studio_info_path(state).exists())
    finally:
        victim.kill()
        victim.wait()


@test
def test_item113_stop_asks_a_live_studio_to_shut_down(ctx: Ctx):
    import tempfile
    from halo_harness.studio.launch import port_answers, stop
    from halo_harness.studio.server import start_server, studio_info_path
    state = Path(tempfile.mkdtemp(prefix="halo-r3c-"))
    srv = start_server(port=0, cwd=state.parent / "proj", state_dir=state)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    bystander = _sleeper()  # the recorded pid belongs to someone else: only the HTTP path may end the Studio
    try:
        studio_info_path(state).write_text(json.dumps({"pid": bystander.pid, "port": srv.server_address[1], "token": srv.token,
                                                   "owner_salt": srv.owner_salt}), encoding="utf-8")  # 3.4.1.2: as `halo studio` writes it
        ok, note = stop(state)
        thread.join(timeout=10)
        ctx.check(f"stop reports a stop, got {ok} {note!r}", ok is True and note.startswith("stopped Studio"))
        ctx.check("the Studio loop ended and the port went quiet", not thread.is_alive() and not port_answers(srv.server_address[1]))
        ctx.check("the process that owned the recorded pid was not touched", bystander.poll() is None)
        ctx.check("studio.json is cleared", not studio_info_path(state).exists())
    finally:
        srv.server_close()
        bystander.kill()
        bystander.wait()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="review3 c tests"))
