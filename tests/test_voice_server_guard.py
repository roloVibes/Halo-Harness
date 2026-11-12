"""tests.test_voice_server_guard -- Halo's speech servers answer only programs on this machine at their own address
(Halo 3.4.1.2, the 2026-11-12 review's SERVERS-7; voice/server_routes.py `_foreign`, voice/server.py `_Http.server_bind`):

1. a request whose Host is another name (a DNS-rebinding page: `evil.example:<port>`) is 403 on GET and POST, and the
   engine is never reached;
2. a request that carries an Origin (a web page's CORS-simple POST, a rebinding page's fetch) is 403, its own too;
3. the server's own loopback names (127.0.0.1, localhost) answer as before;
4. on Windows the listening socket is exclusive (SO_EXCLUSIVEADDRUSE), as Studio's.
"""

from __future__ import annotations

import http.client
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _server():
    from halo_harness.voice.server import _Http
    from halo_harness.voice.server_routes import State, make_handler
    asked: list = []

    class Engine:
        compute = "fake"

        def transcribe(self, *a, **k):
            asked.append("stt")
            return {"text": "hi", "segments": [], "duration": 0.1}
    st = State("stt", "faster-whisper:small.en", "cpu", lambda _l: None, "af_heart")
    st.engine, st.status = Engine(), "ok"
    httpd = _Http(("127.0.0.1", 0), make_handler(st))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, asked


def _ask(port: int, method: str, path: str, headers: dict, body: bytes = b""):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for k, v in headers.items():
            conn.putheader(k, v)
        conn.putheader("Content-Length", str(len(body)))
        conn.endheaders(body)
        r = conn.getresponse()
        return r.status, r.read()
    finally:
        conn.close()


@test
def test_servers_7_a_foreign_host_or_any_origin_is_refused(ctx: Ctx):
    httpd, asked = _server()
    port = httpd.server_address[1]
    try:
        own = {"Host": f"127.0.0.1:{port}"}
        ctx.check("its own address answers /health", _ask(port, "GET", "/health", own)[0] == 200)
        ctx.check("localhost answers too", _ask(port, "GET", "/v1/models", {"Host": f"localhost:{port}"})[0] == 200)
        for heads in ({"Host": f"evil.example:{port}"}, {"Host": "127.0.0.1:1"}, {},
                      {**own, "Origin": "http://evil.example"}, {**own, "Origin": f"http://127.0.0.1:{port}"}):
            ctx.check(f"GET /health with {heads}: 403", _ask(port, "GET", "/health", heads)[0] == 403)
        pcm = b"\0\0" * 1600
        status, _b = _ask(port, "POST", "/v1/audio/transcriptions", {"Host": f"evil.example:{port}",
                                                                     "Content-Type": "audio/pcm;rate=16000"}, pcm)
        ctx.check(f"a rebinding page's POST: 403, got {status}", status == 403)
        status, _b = _ask(port, "POST", "/v1/audio/transcriptions", {**own, "Origin": "http://evil.example",
                                                                     "Content-Type": "text/plain"}, pcm)
        ctx.check(f"a drive-by CORS-simple POST: 403, got {status}", status == 403)
        ctx.check(f"the engine was never reached, got {asked}", not asked)
    finally:
        httpd.shutdown()
        httpd.server_close()


@test
def test_servers_7_the_port_is_exclusive_on_windows(ctx: Ctx):
    httpd, _asked = _server()
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            ctx.check("SO_EXCLUSIVEADDRUSE is set", httpd.socket.getsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE) != 0)
        s = socket.socket()
        try:
            if not hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", httpd.server_address[1]))
                s.listen(1)
                took = True
            except OSError:
                took = False
            ctx.check("a second listener on its port is refused", not took)
        finally:
            s.close()
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
