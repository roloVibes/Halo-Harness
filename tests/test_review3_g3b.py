"""tests.test_review3_g3b -- pins for the 3.0.2.0 review fix pass, round
G3-mcp-commands (part 2): MCP transport/manager behaviour.

  * item 67   a real HTTP 401 on the Streamable HTTP wire (the SDK reports
              it as a bare "Server returned an error response") still
              drives the OAuth refresh retry and the needs_auth state
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all
from tests.helpers.provider_env_defaults import ensure_default_provider_credentials

ensure_default_provider_credentials()

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
PAT = "REALPAT0123456789abcdef"


class _Home:
    """Scoped BRIDGE_TEST_HOME (+ no proxies) for one test."""
    _PROXY = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy")

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", *self._PROXY)}
        for k in self._PROXY:
            os.environ.pop(k, None)
        self.dir = tempfile.mkdtemp(prefix="g3b-")
        os.environ["BRIDGE_TEST_HOME"] = self.dir
        return self.dir

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _server(good_token: str):
    """A stdlib HTTP server speaking just enough Streamable HTTP: any POST
    without `Bearer <good_token>` gets a bare 401; with it, initialize and
    tools/list answer JSON. Returns (server, seen_auth_headers)."""
    seen: list = []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body=b"", ctype="application/json", extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            msg = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            auth = self.headers.get("Authorization", "")
            seen.append(auth)
            if auth != f"Bearer {good_token}":
                return self._send(401, b"", extra={"WWW-Authenticate": 'Bearer realm="x"'})
            method = msg.get("method")
            if method == "initialize":
                result = {"protocolVersion": msg["params"]["protocolVersion"], "capabilities": {"tools": {}},
                          "serverInfo": {"name": "fake", "version": "1"}}
            elif method == "tools/list":
                result = {"tools": []}
            else:
                return self._send(202)
            self._send(200, json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "result": result}).encode())

        def do_GET(self):
            self._send(401 if self.headers.get("Authorization") != f"Bearer {good_token}" else 405,
                       extra={"WWW-Authenticate": 'Bearer realm="x"'})

        def do_DELETE(self):
            self._send(200)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, seen


def _handle(url, name, loop):
    from halo_harness.mcp.manager import McpServerConfig, McpServerHandle
    cfg = McpServerConfig(name=name, type="http", url=url, scope="user")
    return McpServerHandle(cfg, loop, tool_env=dict(os.environ), cwd=REPO, trusted=True)


# ---- item 67: a real 401 over Streamable HTTP --------------------------------

@test
def test_item67_real_401_marks_needs_auth(ctx: Ctx):
    from halo_harness.mcp.client import McpLoop
    with _Home():
        srv, seen = _server("good-token")
        loop = McpLoop()
        h = _handle(f"http://127.0.0.1:{srv.server_port}/mcp", "g3b-noauth", loop)
        try:
            h.start()
            ctx.check(f"state is needs_auth, got {h.state!r} ({h.error})", h.state == "needs_auth")
            ctx.check("the error names the HTTP status", "401" in (h.error or ""))
        finally:
            h.close()
            loop.close()
            srv.shutdown()


@test
def test_item67_real_401_refreshes_the_oauth_token_and_reconnects(ctx: Ctx):
    from halo_harness.mcp import oauth
    from halo_harness.mcp.client import McpLoop
    with _Home():
        oauth.save_tokens("g3b-refresh", {"access_token": "stale", "refresh_token": "rt"})
        orig = oauth.refresh_tokens
        oauth.refresh_tokens = lambda name, stored, *, oauth_cfg, server_url: (
            {"access_token": "good-token", "refresh_token": "rt"}, None)
        srv, seen = _server("good-token")
        loop = McpLoop()
        h = _handle(f"http://127.0.0.1:{srv.server_port}/mcp", "g3b-refresh", loop)
        try:
            h.start()
            ctx.check(f"connected after the refresh, got {h.state!r} ({h.error})", h.state == "connected")
            ctx.check(f"stale token tried first, refreshed token second, got {seen[:2]}",
                      seen[:1] == ["Bearer stale"] and "Bearer good-token" in seen[1:])
        finally:
            oauth.refresh_tokens = orig
            h.close()
            loop.close()
            srv.shutdown()


@test
def test_item67_recorded_status_helpers(ctx: Ctx):
    from halo_harness.mcp import http_sse
    wrapped = http_sse.with_recorded_status(RuntimeError("Server returned an error response"), {"status": 401})
    ctx.check("401 is wrapped with the status in the text", http_sse.looks_like_auth_required(wrapped)
              and "401" in str(wrapped))
    plain = RuntimeError("Server returned an error response")
    ctx.check("a 500 is not auth", http_sse.with_recorded_status(plain, {"status": 500}) is plain)
    ctx.check("403 without a Bearer challenge is not auth", http_sse.with_recorded_status(plain, {"status": 403}) is plain)
    ctx.check("403 with a Bearer challenge is auth",
              http_sse.looks_like_auth_required(
                  http_sse.with_recorded_status(plain, {"status": 403, "challenge": 'Bearer realm="x"'})))
    cancelled = BaseException("stop")
    ctx.check("non-Exception (cancellation) passes through untouched",
              http_sse.with_recorded_status(cancelled, {"status": 401}) is cancelled)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
