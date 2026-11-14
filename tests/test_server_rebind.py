"""tests.test_server_rebind -- Halo 3.4.1.1 (the 3.4.1.0 R6 open item): every server Halo starts that a user restarts on
the same port binds like Studio does (tests/test_studio_rebind.py). On POSIX a connection the server closed first sits
in TIME_WAIT on its port for a minute, and a listener without SO_REUSEADDR could not bind it until then: `halo host
serve` (its fixed port) and a speech server's own door (`halo voice serve --port N`) now set it on
POSIX, where it never lets two listeners share a port; Windows keeps its default (the host also sets
SO_EXCLUSIVEADDRUSE there). Each class's own bind policy is exercised through a stand-in handler:

1. a request it answered and closed, then stop: the same port binds again at once, no retry;
2. a second listener on a port a running one serves is still refused (OSError), on every platform.
The remote control socket binds port 0 or a Unix socket (never a fixed port), and a local model server's own door is
the engine's (llama.cpp, MLX), not Halo's: neither applies. Run: python -m tests.test_server_rebind
"""
from __future__ import annotations

import http.client
import http.server
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_scoped_state_dir_once  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

ensure_scoped_state_dir_once()
test, TESTS = new_registry()


class _Ok(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *_a):
        pass


def _classes() -> dict:
    from halo_harness.host import service
    from halo_harness.voice import server as voice
    return {"the host door (halo host serve)": service._Server, "a speech server's door (halo voice serve)": voice._Http}


def _stand_in(cls):
    class T(cls):  # the class's own allow_reuse_address and server_bind; a handler that answers and closes
        def __init__(self, addr):
            self.svc = self.hub = self.ssl_ctx = None
            http.server.ThreadingHTTPServer.__init__(self, addr, _Ok)
    return T


def _serve(T, port: int):
    srv = T(("127.0.0.1", port))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _stop(srv) -> None:
    srv.shutdown()
    srv.server_close()


@test
def test_each_server_binds_its_port_again_at_once(ctx: Ctx):
    for name, cls in _classes().items():
        T = _stand_in(cls)
        srv = _serve(T, 0)
        port = srv.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("GET", "/")
        ok = conn.getresponse().status == 200
        conn.close()
        _stop(srv)
        try:
            again = _serve(T, port)
            _stop(again)
            bound = True
        except OSError as e:
            bound = f"{type(e).__name__}: {e}"
        ctx.check(f"{name}: answered, stopped, and serves again on port {port} at once, got {ok} {bound}", ok and bound is True)
        posix = sys.platform != "win32"
        ctx.check(f"{name}: SO_REUSEADDR on POSIX only", cls.allow_reuse_address is posix)


@test
def test_a_second_listener_on_a_served_port_is_refused(ctx: Ctx):
    for name, cls in _classes().items():
        T = _stand_in(cls)
        first = _serve(T, 0)
        try:
            try:
                second = T(("127.0.0.1", first.server_address[1]))
                second.server_close()
                refused = False
            except OSError:
                refused = True
            ctx.check(f"{name}: a second listener on its port is refused", refused)
        finally:
            _stop(first)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
