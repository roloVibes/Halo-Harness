"""halo_harness.studio.server -- `halo studio`: a loopback-only HTTP server
that serves the Studio page and its JSON API (Halo 2.1.0 round B3).

Security model: binds 127.0.0.1 on a random port (or --port); a per-launch
token goes into the URL fragment the browser opens with and must come back
as `Authorization: Bearer` on every /api call; a request from a non-loopback
peer, or one carrying an Origin that is not this server's own, is refused
before any handler runs. Nothing is written outside ~/.halo (and a project's
.halo/ when the page chooses project scope). Stdlib only, like bridge.py.
"""

from __future__ import annotations

import argparse
import hmac
import http.server
import json
import mimetypes
import os
import secrets
import socket
import sys
import threading
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

STATIC = Path(__file__).resolve().parent / "static"
LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, addr, handler, *, token: str, cwd: Path, state_dir: Path):
        self.token, self.cwd, self.state_dir = token, cwd, state_dir
        super().__init__(addr, handler)

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    timeout = 60

    def log_message(self, fmt, *args):  # quiet unless HALO_STUDIO_LOG is set
        if os.environ.get("HALO_STUDIO_LOG"):
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    # -- plumbing ---------------------------------------------------------------
    def _send(self, status: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, obj) -> None:
        self._send(status, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"), "application/json; charset=utf-8")

    def _own_origin(self) -> set:
        port = self.server.server_address[1]
        return {f"http://127.0.0.1:{port}", f"http://localhost:{port}", f"http://[::1]:{port}"}

    def _guard(self) -> bool:
        """Loopback peer, own Origin (when one is sent), the launch token."""
        if self.client_address[0] not in LOOPBACK:
            self._json(403, {"error": "studio only answers the local machine"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in self._own_origin():
            self._json(403, {"error": "foreign origin"})
            return False
        auth = self.headers.get("Authorization", "")
        presented = auth[7:] if auth.startswith("Bearer ") else ""
        if not presented or not hmac.compare_digest(presented, self.server.token):
            self._json(401, {"error": "missing or wrong studio token: open the URL `halo studio` printed"})
            return False
        return True

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        if n > (22_000_000 if self.path.startswith("/api/design/") and self.path.endswith("/assets") else 4_000_000):  # a design asset is 15 MB base64
            raise ValueError("body too large")
        data = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {"value": data}

    # -- routing ----------------------------------------------------------------
    def _api(self, method: str) -> None:
        from halo_harness.studio.api import Request, dispatch
        if not self._guard():
            return
        parts = urlsplit(self.path)
        path = unquote(parts.path)[len("/api/"):]
        query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        try:
            body = self._body() if method in ("POST", "PUT", "PATCH") else {}
        except ValueError as e:
            self._json(400, {"error": f"bad JSON body: {e}"})
            return
        req = Request(method=method, path=path, query=query, body=body, cwd=self.server.cwd, state_dir=self.server.state_dir)
        try:
            status, obj = dispatch(req)
        except Exception as e:  # a handler bug must never take the server down
            status, obj = 500, {"error": f"{type(e).__name__}: {e}"}
        self._json(status, obj)

    def _static(self) -> None:
        if self.client_address[0] not in LOOPBACK:
            self._json(403, {"error": "studio only answers the local machine"})
            return
        rel = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
        target = (STATIC / rel).resolve()
        if STATIC not in target.parents or not target.is_file():
            self._json(404, {"error": "not found"})
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype, {"Content-Security-Policy": "default-src 'self'; img-src 'self' data: http://127.0.0.1:* http://localhost:*; style-src 'self' 'unsafe-inline'; frame-src http://127.0.0.1:* http://localhost:*"})

    def _design_file(self) -> None:
        """3.0.1.0 D3: a design artboard's raw file for the page's sandboxed iframes (its own CSP, loopback only)."""
        from halo_harness.studio import design_files
        if self.client_address[0] not in LOOPBACK:
            self._json(403, {"error": "studio only answers the local machine"})
            return
        parts = urlsplit(self.path)
        status, body, ctype = design_files.read(self.server.state_dir, parts.path, {k: v[-1] for k, v in parse_qs(parts.query).items()})
        self._send(status, body, ctype, {"Content-Security-Policy": design_files.CSP})

    def do_GET(self):
        if self.path.startswith("/design-files/"):
            self._design_file()
        else:
            self._api("GET") if self.path.startswith("/api/") else self._static()

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        self._api("POST")

    def do_PUT(self):
        self._api("PUT")

    def do_PATCH(self):
        self._api("PATCH")

    def do_DELETE(self):
        self._api("DELETE")


# -- the command ------------------------------------------------------------------

def studio_info_path(state_dir: Path) -> Path:
    return Path(state_dir) / "studio.json"


def start_server(*, port: int = 0, cwd: Path, state_dir: Path, token: str | None = None) -> _Server:
    token = token or secrets.token_urlsafe(24)
    server = _Server(("127.0.0.1", port), Handler, token=token, cwd=cwd, state_dir=state_dir)
    return server


def url_for(server: _Server) -> str:
    return f"http://127.0.0.1:{server.server_address[1]}/#t={server.token}"


_BACKGROUND: dict = {}


def ensure_background(*, cwd: Path, state_dir: Path, open_browser: bool = True) -> str:
    """`/studio` from a live session: start the server in a daemon thread of
    THIS process once (a second call reuses it) and return the URL. The
    server dies with the session; nothing is left behind."""
    srv = _BACKGROUND.get("server")
    if srv is None:
        srv = start_server(port=0, cwd=cwd, state_dir=state_dir)
        threading.Thread(target=srv.serve_forever, name="halo-studio", daemon=True).start()
        _BACKGROUND["server"] = srv
    url = url_for(srv)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return url


def cmd_studio(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo studio", description="Open Halo Studio: your lineups and agent bios as an editable graph.")
    parser.add_argument("--port", type=int, default=0, help="port to listen on (default: a free one)")
    parser.add_argument("--no-open", action="store_true", help="print the URL, do not open a browser")
    parser.add_argument("--cwd", default=None, help="the project directory for project-scope files (default: the current directory)")
    args = parser.parse_args(argv)
    from halo_harness.providers.config import default_state_dir
    state_dir = Path(default_state_dir())
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    try:
        server = start_server(port=args.port, cwd=cwd, state_dir=state_dir)
    except OSError as e:
        print(f"halo studio: cannot bind 127.0.0.1:{args.port or 'auto'}: {e}", file=sys.stderr)
        return 1
    url = url_for(server)
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        studio_info_path(state_dir).write_text(json.dumps({"pid": os.getpid(), "port": server.server_address[1]}), encoding="utf-8")
    except OSError:
        pass
    print(f"Halo Studio is at {url}")
    print("Over SSH: ssh -L {p}:127.0.0.1:{p} <host>, then open the same URL on your machine.".format(p=server.server_address[1]))
    print("Ctrl+C stops it.")
    if not args.no_open:
        try:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstudio stopped")
    finally:
        server.server_close()
        try:
            studio_info_path(state_dir).unlink()
        except OSError:
            pass
    return 0
