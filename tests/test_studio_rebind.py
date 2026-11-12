"""tests.test_studio_rebind -- Studio serves again on its own port right after it stopped (Halo 3.4.1.0 R6).

The 3.4.1.0 candidate's glance driver stops Studio and serves it again on the same port; on GitHub's Linux runner the
port "did not come back": a connection Studio closed first sits in TIME_WAIT on that port for a minute, and a listener
without SO_REUSEADDR cannot bind it until then (a user restarting `halo studio --port N` met the same). Studio now sets
SO_REUSEADDR on POSIX, where it never lets two listeners share a port, and keeps SO_EXCLUSIVEADDRUSE on Windows:

1. a request Studio answered and closed, then stop: start_server on the same port binds at once, no retry;
2. a second Studio on a port a running one serves is still refused (OSError), on every platform.
Run: python -m tests.test_studio_rebind
"""
from __future__ import annotations

import socket
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _serve(state: Path, port: int = 0):
    from halo_harness.studio.server import start_server
    srv = start_server(port=port, cwd=state.parent / "proj", state_dir=state, slow_ms=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _stop(srv) -> None:
    srv.shutdown()
    srv.server_close()


def _answered_and_closed(port: int) -> bytes:
    """One HTTP/1.0 request: Studio answers and closes the connection first (its side goes to TIME_WAIT)."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(b"GET /api/health HTTP/1.0\r\nHost: 127.0.0.1:%d\r\n\r\n" % port)
        got = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                return got
            got += chunk


@test
def test_studio_binds_its_port_again_right_after_it_stopped(ctx: Ctx):
    state = Path(tempfile.mkdtemp(prefix="halo-rebind-")) / "home"
    state.mkdir()
    srv = _serve(state)
    port = srv.server_address[1]
    reply = _answered_and_closed(port)
    ctx.check(f"Studio answered and closed the connection, got {reply[:40]!r}", reply.startswith(b"HTTP/1."))
    _stop(srv)
    again = None
    try:
        again = _serve(state, port)
        ctx.check(f"served again on {port} at once", again.server_address[1] == port)
        reply = _answered_and_closed(port)
        ctx.check(f"and answers there, got {reply[:40]!r}", reply.startswith(b"HTTP/1."))
    except OSError as e:
        ctx.check(f"served again on {port} at once, got {e!r}", False)
    finally:
        if again is not None:
            _stop(again)


@test
def test_two_studios_never_share_a_port(ctx: Ctx):
    state = Path(tempfile.mkdtemp(prefix="halo-rebind-")) / "home"
    state.mkdir()
    srv = _serve(state)
    port = srv.server_address[1]
    try:
        try:
            other = _serve(state, port)
            _stop(other)
            ctx.check(f"a second Studio on {port} is refused", False)
        except OSError as e:
            ctx.check(f"a second Studio on {port} is refused: {e.__class__.__name__}", True)
    finally:
        _stop(srv)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio rebind"))
