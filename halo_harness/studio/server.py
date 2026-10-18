"""halo_harness.studio.server -- `halo studio`: a loopback-only HTTP server
that serves the Studio page and its JSON API (Halo 2.1.0 round B3).

Security model: binds 127.0.0.1 on a random port (or --port); a per-launch
token goes into the URL fragment the browser opens with and must come back
as `Authorization: Bearer` on every /api call; a request from a non-loopback
peer, or one carrying an Origin that is not this server's own, is refused
before any handler runs, and so is one whose Host header is not this
server's own loopback address and port (a DNS-rebinding page). Nothing is
written outside ~/.halo (and a project's .halo/ when the page chooses project
scope). Stdlib only, like bridge.py.
"""

from __future__ import annotations

import argparse
import hmac
import http.server
import json
import mimetypes
import os
import secrets
import signal
import socket
import sys
import threading
import webbrowser
from typing import Optional
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

STATIC = Path(__file__).resolve().parent / "static"
DIST = STATIC / "dist"      # 3.0.3.0: the React shell's committed build (halo_harness/studio/ui); 3.0.7.0 R2: the only page
SHELL_CSP = ("default-src 'self'; connect-src 'self'; img-src 'self' data:; style-src 'self'; "
             "frame-src 'self' http://127.0.0.1:* http://localhost:*")
# 3.0.7.0 R2: the classic page (static/legacy) is gone; a checkout without a build gets this one line at `/`
NO_BUILD = (b"<!doctype html><meta charset=\"utf-8\"><title>Halo Studio</title>"
            b"<p>Build the Studio UI first: <code>cd halo_harness/studio/ui &amp;&amp; npm ci &amp;&amp; npm run build</code> "
            b"(docs/DEVELOPMENT.md).</p>")
LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, addr, handler, *, token: str, cwd: Path, state_dir: Path):
        self.token, self.cwd, self.state_dir = token, cwd, state_dir
        self.events = None  # studio.events.EventBridge, made by the first /api/events
        self.fleet_hub = None  # 3.0.5.0 R2: fleet.hub.HubServer (`halo studio --fleet`, studio/fleet_hub_api.py)
        self.events_lock = threading.Lock()
        super().__init__(addr, handler)

    def server_close(self):
        if getattr(self, "fleet_watch", None) is not None:  # 3.0.5.0 R4: studio/fleet_watch.py
            self.fleet_watch.stop()
        if self.events is not None:
            self.events.close()
        if self.fleet_hub is not None:  # the fleet hub ends with Studio
            self.fleet_hub.stop()
        super().server_close()

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
        if status >= 400:  # a refused request may leave its body unread: do not parse it as the next request line
            self.close_connection = True
            self.send_header("Connection", "close")
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

    def _local_only(self) -> bool:
        """Loopback peer and a Host header that names this server (127.0.0.1, localhost or [::1] on its own port)."""
        if self.client_address[0] not in LOOPBACK:
            self._json(403, {"error": "studio only answers the local machine"})
            return False
        host = (self.headers.get("Host") or "").strip().lower()
        name, _, port = host.rpartition(":") if not host.endswith("]") else (host, "", "")
        if name not in ("127.0.0.1", "localhost", "[::1]") or port != str(self.server.server_address[1]):
            self._json(403, {"error": "studio only answers its own address: open the URL `halo studio` printed"})
            return False
        return True

    def _guard(self) -> bool:
        """Loopback peer and Host, own Origin (when one is sent), the launch token."""
        if not self._local_only():
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
        big = self.path.startswith(("/api/design/", "/api/flow/")) and urlsplit(self.path).path.endswith("/assets")
        if n > (22_000_000 if big else 4_000_000):  # a design or flow asset is 15 MB base64
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
        if method == "POST" and path == "shutdown":  # `halo studio --stop`: end serve_forever so studio.json is removed
            self._json(200, {"ok": True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        query = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        try:
            body = self._body() if method in ("POST", "PUT", "PATCH") else {}
        except ValueError as e:
            self._json(400, {"error": f"bad JSON body: {e}"})
            return
        req = Request(method=method, path=path, query=query, body=body, cwd=self.server.cwd, state_dir=self.server.state_dir,
                      server=self.server)
        try:
            status, obj = dispatch(req)
        except Exception as e:  # a handler bug must never take the server down
            status, obj = 500, {"error": f"{type(e).__name__}: {e}"}
        from halo_harness.studio.raw_body import RawBody  # 3.0.5.0 R4: a recording's HTML, not JSON
        if isinstance(obj, RawBody):
            return self._send(status, obj.body, obj.ctype, obj.headers)
        self._json(status, obj)

    def _static(self) -> None:
        """Everything from static/dist (the shell). 3.0.7.0 R2: there is no
        classic page any more; a checkout without a build answers `/` with
        one line saying how to build the UI."""
        if not self._local_only():
            return
        rel = unquote(urlsplit(self.path).path).lstrip("/") or "index.html"
        if not (DIST / "index.html").is_file():
            if rel == "index.html":
                self._send(200, NO_BUILD, "text/html; charset=utf-8", {"Content-Security-Policy": SHELL_CSP})
            else:
                self._json(404, {"error": "not found: the Studio UI is not built (docs/DEVELOPMENT.md)"})
            return
        cand = (DIST / rel).resolve()
        if DIST.resolve() not in cand.parents or not cand.is_file():
            self._json(404, {"error": "not found"})
            return
        ctype = mimetypes.guess_type(str(cand))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, cand.read_bytes(), ctype, {"Content-Security-Policy": SHELL_CSP})

    def _design_file(self) -> None:
        """3.0.1.0 D3: a design artboard's raw file for the page's sandboxed iframes (its own CSP, loopback only)."""
        from halo_harness.studio import design_files
        if not self._local_only():
            return
        parts = urlsplit(self.path)
        status, body, ctype = design_files.read(self.server.state_dir, parts.path, {k: v[-1] for k, v in parse_qs(parts.query).items()})
        self._send(status, body, ctype, {"Content-Security-Policy": design_files.csp_for(ctype)})

    def do_GET(self):
        if urlsplit(self.path).path == "/api/events":  # streams: before the JSON dispatch
            from halo_harness.studio.events import serve_sse
            serve_sse(self)
        elif self.path.startswith("/design-files/"):
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


STUDIO_MODES = ("roles", "org", "design", "orchestra", "flow", "fleet", "team")  # 3.0.4.0: the shell's sections too; 3.0.5.0: Fleet; 3.0.8.0: Team


def url_for(server: _Server, mode: Optional[str] = None, edit: Optional[str] = None) -> str:
    """The page URL with the per-launch token. `mode` (3.0.2.0: roles |
    org | design; then every section of the shell) lands in the query so the
    page opens straight into it, ahead of the saved mode; the token stays in
    the fragment. `edit` (3.1.1.0 R3, studio/edit_target.py: bio:<name>,
    lineup:<name>, team) adds `&edit=` and picks the mode."""
    from halo_harness.studio.launch import _query
    query = _query(mode, edit)
    return f"http://127.0.0.1:{server.server_address[1]}/{query}#t={server.token}"


_BACKGROUND: dict = {}


def ensure_background(*, cwd: Path, state_dir: Path, open_browser: bool = True, mode: Optional[str] = None) -> str:
    """`/studio` from a live session: start the server in a daemon thread of
    THIS process once (a second call reuses it) and return the URL. The
    server dies with the session; nothing is left behind."""
    srv = _BACKGROUND.get("server")
    if srv is None:
        srv = start_server(port=0, cwd=cwd, state_dir=state_dir)
        threading.Thread(target=srv.serve_forever, name="halo-studio", daemon=True).start()
        _BACKGROUND["server"] = srv
    url = url_for(srv, mode)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return url


def cmd_studio(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="halo studio", description="Open Halo Studio, the browser GUI: Roles (lineups and agent bios as a graph), Org (the company in Paperclip) and Design (artboards on your own apps).")
    parser.add_argument("--mode", choices=STUDIO_MODES, default=None, help="open straight into roles, org, design, orchestra, flow, fleet or team (default: the mode you used last)")
    parser.add_argument("--port", type=int, default=0, help="port to listen on (default: a free one)")
    parser.add_argument("--no-open", action="store_true", help="print the URL, do not open a browser")
    parser.add_argument("--cwd", default=None, help="the project directory for project-scope files (default: the current directory)")
    parser.add_argument("--stop", action="store_true", help="stop the Studio that is running in the background (the wizard's Open Studio buttons start one)")
    parser.add_argument("--fleet", action="store_true", help="also run the fleet hub in this process: other harnesses join it with `halo fleet join` (docs/FLEET.md)")
    parser.add_argument("--edit", default=None, metavar="TARGET", help="open Studio on bio:<name> (its form), lineup:<name> (its inspector) or team; a Studio already running for this home opens it in its open page")
    args = parser.parse_args(argv)
    edit = None
    if args.edit:  # 3.1.1.0 R3: Studio is the editor of bios and lineups
        from halo_harness.studio.edit_target import parse
        edit, why = parse(args.edit)
        if edit is None:
            print(f"halo studio: --edit: {why}", file=sys.stderr)
            return 2
        args.mode = edit.mode
    from halo_harness.providers.config import default_state_dir
    state_dir = Path(default_state_dir())
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd()
    from halo_harness.studio.launch import existing_url, stop
    if args.stop:
        ok, note = stop(state_dir)
        print(f"halo studio: {note}")
        return 0 if ok else 1
    if edit is not None and not args.port and existing_url(state_dir, args.mode):
        from halo_harness.studio.edit_open import describe, open_edit
        print(describe(open_edit(edit, cwd=cwd, state_dir=state_dir, open_browser=not args.no_open)))
        return 0
    running = existing_url(state_dir, args.mode)
    if running and not args.port:  # 3.0.2.0: one Studio per machine -- reuse it
        print(f"Halo Studio is already running at {running}")
        print("halo studio --stop stops it.")
        if not args.no_open:
            try:
                webbrowser.open(running)
            except Exception:
                pass
        return 0
    try:
        server = start_server(port=args.port, cwd=cwd, state_dir=state_dir)
    except OSError as e:
        print(f"halo studio: cannot bind 127.0.0.1:{args.port or 'auto'}: {e}", file=sys.stderr)
        return 1
    url = url_for(server, args.mode, edit.text if edit is not None else None)
    if args.fleet:  # 3.0.5.0 R2: the fleet hub inside Studio's process
        from halo_harness.studio.fleet_hub_api import start_for_flag
        print(start_for_flag(server, state_dir))
    try:
        state_dir.mkdir(parents=True, exist_ok=True)
        from halo_harness.privateio import write_private_atomic
        write_private_atomic(studio_info_path(state_dir),
                             json.dumps({"pid": os.getpid(), "port": server.server_address[1], "token": server.token}))
    except OSError:
        pass
    print(f"Halo Studio is at {url}")
    print("Over SSH: ssh -L {p}:127.0.0.1:{p} <host>, then open the same URL on your machine.".format(p=server.server_address[1]))
    print("Ctrl+C stops it (from another shell: halo studio --stop).")
    if not args.no_open:
        try:
            threading.Timer(0.3, lambda: webbrowser.open(url)).start()
        except Exception:
            pass
    def _on_term(*_a):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, _on_term)  # a plain `kill` also reaches the finally below
    except (ValueError, OSError):
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
