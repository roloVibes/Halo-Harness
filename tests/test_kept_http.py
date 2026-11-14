"""tests.test_kept_http -- Halo 3.6.0.0 R3: the rigs' calls to a local server keep their connection
(tests/helpers/kept_http.py), so a module no longer spends a local port per call (Windows holds a closed client's
port in TIME_WAIT for about two minutes, and four Chrome shards beside the fast ones ran the range dry: WinError
10048 from a rig's own connect).

1. a hundred calls to Studio's server over one thread make one connection; an error status (the server closes the
   connection after it) is answered and the next call opens a new one;
2. a connect that finds no free local port is tried again for a short bounded time, and any other error is not.
Run: python -m tests.test_kept_http
"""
from __future__ import annotations

import errno
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.config_seed import ConfigHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_one_connection_for_many_calls(ctx: Ctx):
    from halo_harness.studio.server import start_server
    with ConfigHome() as home:
        _calls(ctx, start_server(port=0, cwd=home.home, state_dir=home.state))


def _calls(ctx: Ctx, srv) -> None:
    from halo_harness.studio.owner_proof import HEADER, header_for
    from tests.helpers import kept_http
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    made: list = []
    orig = kept_http._open

    def counting(port, timeout):
        made.append(port)
        return orig(port, timeout)
    kept_http._open = counting
    try:
        heads = {"Authorization": "Bearer " + srv.token, HEADER: header_for(srv)}
        port = srv.server_address[1]
        codes = [kept_http.request(port, "GET", "/api/builder", None, heads)[0] for _ in range(100)]
        ctx.check(f"a hundred answers, got {set(codes)}", codes == [200] * 100)
        ctx.check(f"one connection for them, got {len(made)}", len(made) == 1)
        bad = kept_http.request(port, "GET", "/api/builder", None, {"Authorization": "Bearer wrong"})[0]
        ctx.check(f"the wrong token is answered 401, got {bad}", bad == 401)
        again = kept_http.request(port, "GET", "/api/builder", None, heads)[0]
        ctx.check(f"after the server closed it, a new connection answers, got {again} ({len(made)} made)", again == 200 and len(made) == 2)
    finally:
        kept_http._open = orig
        srv.shutdown()
        srv.server_close()


@test
def test_a_port_number_that_comes_back_is_not_the_old_server(ctx: Ctx):
    """Server A closes its listener (its kept connection's handler thread lives on); server B gets A's port number.
    A call that names B is answered by B, not over the connection kept for A."""
    import http.server
    from tests.helpers import kept_http

    def make(name: str, port: int):
        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):  # noqa: N802
                data = name.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv

    a = make("a", 0)
    port = a.server_address[1]
    b = None
    try:
        first = kept_http.request(port, "GET", "/", None, {}, timeout=10, who="a")[1]
        a.shutdown()
        a.server_close()
        b = make("b", port)
        second = kept_http.request(port, "GET", "/", None, {}, timeout=10, who="b")[1]
        ctx.check(f"A answered A's call and B answered B's, got {first!r} {second!r}", (first, second) == (b"a", b"b"))
    finally:
        conn = kept_http._conns().pop(port, (None, ""))[0]
        if conn is not None:
            conn.close()
        if b is not None:
            b.shutdown()
            b.server_close()


@test
def test_a_connect_with_no_free_port_is_tried_again(ctx: Ctx):
    from tests.helpers import kept_http
    tries: list = []

    def flaky():
        tries.append(1)
        if len(tries) < 3:
            e = OSError(errno.EADDRINUSE, "Only one usage of each socket address")
            raise e
        return "open"
    ctx.check("the third try opens it", kept_http.connect(flaky, seconds=2.0) == "open" and len(tries) == 3)

    def refused():
        raise ConnectionRefusedError(errno.ECONNREFUSED, "refused")
    try:
        kept_http.connect(refused, seconds=2.0)
        ctx.check("a refused connect raises", False)
    except ConnectionRefusedError:
        ctx.check("a refused connect raises at once", True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
