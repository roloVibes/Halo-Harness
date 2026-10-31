"""halo_harness.host.http -- the host's signed routes (Halo 3.3.7.0 R1 + R2; docs/HOST.md has the table).

    POST /host/v1/join                 {v, harness, a, ts, nonce, mac}: the six-word code authenticates it (the hub's
                                       exchange, fleet/hub_join.py); the reply adds `serves` [{name, port, addr}]
    GET  /host/v1/ping | card | catalog?window=N | profiles | events?since=&kind= | tail?n=&host= | stream
    POST /host/v1/simulate {model | size_gb, window, kv?}    POST /host/v1/route {need: {...}}
    R2 (host/routes_act.py): POST control/<op> | manage/<op> | admin/<op> | request; GET me | job/<id> | jobs |
                             changes | findings | pending; POST ledger {lines} (host/ledger_take.py)

Every route but `join` carries fleet/protocol.py's HMAC headers made with the peer's pair key (the 120 s window, the
replay guard): an unknown peer gets 403, a wrong key or a stale or replayed request 401. Every request writes one
audit line (host/state.audit; an acting request's line adds its op, params, evidence, dry, landed, change and job).
The view routes read; the acting routes are the typed vocabulary (host/ops.py) -- nothing here runs a model,
changes a server setting or restarts a server.
"""

from __future__ import annotations

import http.server
import json
import os
import sys
import time
from urllib.parse import parse_qs, urlsplit

from halo_harness.fleet import protocol

PREFIX = "/host/v1"
MAX_BODY = 256_000
GETS = ("ping", "card", "catalog", "profiles", "events", "tail", "stream", "me", "job", "jobs", "changes", "findings",
        "pending")
POSTS = ("simulate", "route", "request", "ledger")
GRANTED = ("control", "manage", "admin")


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HaloHost/1"
    timeout = 30

    def log_message(self, fmt, *args):
        if os.environ.get("HALO_HOST_LOG"):
            sys.stderr.write("halo host %s - %s\n" % (self.address_string(), fmt % args))

    @property
    def svc(self):
        return self.server.svc

    def _json(self, status: int, obj) -> None:
        body = protocol.encode(obj)
        self.send_response(status)
        for k, v in (("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(body))),
                     ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff")):
            self.send_header(k, v)
        if status >= 400:
            self.close_connection = True
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self._status = status

    def _route(self) -> str:
        path = urlsplit(self.path).path
        return path[len(PREFIX) + 1:] if path.startswith(PREFIX + "/") else ""

    def _query(self) -> dict:
        return {k: v[-1] for k, v in parse_qs(urlsplit(self.path).query).items()}

    def _peer(self, raw: bytes):
        """The peer's harness id, or None after answering 401 / 403."""
        hid, why = protocol.check_headers(self.headers, self.command, self.path, raw, self.svc.pairing.key_for,
                                          self.svc.guard)
        if hid:
            self._who = (self.svc.pairing.member(hid) or {}).get("name") or hid[:8]
            return hid
        if why == "unknown member":
            self._json(403, {"error": "not a peer of this host (never paired, or removed): `halo host pair` here, "
                                      "then `halo host join` there"})
        else:
            self._json(401, {"error": f"request refused: {why}"})
        return None

    def _audited(self, fn) -> None:
        from halo_harness.ollama_steward.host_client import serving
        t0, self._status, self._who = time.monotonic(), 0, str(self.headers.get(protocol.H_MEMBER) or "")[:16]
        self._act: dict = {}
        try:
            with serving():
                fn()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as e:  # one bad answer never takes the host down
            try:
                self._json(500, {"error": f"{type(e).__name__}: {e}"[:300]})
            except OSError:
                pass
        finally:
            from halo_harness.host.state import audit
            audit(self.svc.home, self._who, self.path, 200 <= (self._status or 0) < 300,
                  (time.monotonic() - t0) * 1000.0, extra=self._act)

    # ---- GET ----------------------------------------------------------------------------------
    def do_GET(self):
        self._audited(self._get)

    def _get(self) -> None:
        route = self._route()
        if route.split("/", 1)[0] not in GETS:
            return self._json(404, {"error": "this port serves only the Halo host protocol (/host/v1)"})
        hid = self._peer(b"")
        if not hid:
            return None
        q, view = self._query(), self.svc.view
        from halo_harness.host import routes_act
        got = routes_act.get(self.svc, route, q, hid)
        if got is not None:
            return self._json(*got)
        if route == "ping":
            return self._json(200, protocol.doc(ok=True, host=self.svc.public(), you={"name": self._who,
                                                                                       "grants": list(self._grants())}))
        if route == "stream":
            from halo_harness.host.stream import serve
            return serve(self)
        if route == "card":
            from halo_harness.host.state import audit_summary
            return self._json(200, protocol.doc(host=self.svc.public(), audit=audit_summary(self.svc.home), **view.card()))
        if route == "catalog":
            from halo_harness.host.answers import _window
            return self._json(200, protocol.doc(**view.catalog(_window(q.get("window")))))
        if route == "profiles":
            return self._json(200, protocol.doc(**view.profiles()))
        if route == "events":
            since = q.get("since") or None
            try:
                since = float(since) if since is not None else None
            except ValueError:
                pass  # a span such as "24h" (server_events.read_events reads it)
            return self._json(200, protocol.doc(**view.events(since, q.get("kind") or None)))
        try:
            n = int(q.get("n") or 200)
        except ValueError:
            return self._json(422, {"error": "n is a number of lines"})
        return self._json(200, protocol.doc(**view.tail(n, q.get("host") or "")))

    def _grants(self) -> tuple:
        hid = str(self.headers.get(protocol.H_MEMBER) or "")
        return self.svc.pairing.grants_of(hid)

    # ---- POST ---------------------------------------------------------------------------------
    def do_POST(self):
        self._audited(self._post)

    def _post(self) -> None:
        route = self._route()
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n > MAX_BODY:
            return self._json(413, {"error": "body too large"})
        raw = self.rfile.read(n) if n > 0 else b""
        if route == "join":
            return self._join(raw)
        head = route.split("/", 1)[0]
        if route not in POSTS and head not in GRANTED:
            return self._json(404, {"error": "this port serves only the Halo host protocol (/host/v1)"})
        hid = self._peer(raw)
        if not hid:
            return None
        if head in GRANTED or route == "request":
            from halo_harness.host.routes_act import post
            status, out, self._act = post(self.svc, route, raw, hid)
            return self._json(status, protocol.doc(**out) if status < 400 else out)
        if route == "ledger":
            from halo_harness.host.ledger_take import take
            return self._json(*take(self.svc, raw, hid, self._who))
        try:
            body = protocol.decode(raw)
        except ValueError as e:
            return self._json(400, {"error": f"bad request: {e}"})
        from halo_harness.host import answers
        status, out = (answers.simulate if route == "simulate" else answers.route)(self.svc.view, body)
        return self._json(status, protocol.doc(**out) if status == 200 else out)

    def _join(self, raw: bytes) -> None:
        from halo_harness.fleet.hub_join import handle_join
        from halo_harness.host.state import DEFAULT_GRANTS, served_rows
        try:
            body = protocol.decode(raw)
        except ValueError as e:
            return self._json(400, {"error": f"bad join request: {e}"})
        self._who = str(((body.get("harness") or {}) if isinstance(body.get("harness"), dict) else {}).get("name") or "")[:16]
        status, reply = handle_join(self.svc, body, self.client_address[0], self.svc.gate)
        if status in (403, 409):
            reply = {"error": "that pairing code was not accepted (wrong, already used or expired); run `halo host "
                              "pair` on the host for a new one" if status == 403 else "that is this host's own harness: "
                              "it reads this machine's servers directly, with no pairing"}
        if status == 200:
            hid = str((body.get("harness") or {}).get("id") or "")
            self.svc.pairing.update_member(hid, grants=list(DEFAULT_GRANTS))
            reply = {**reply, "serves": served_rows(self.svc.addr(), self.svc.view.hosts()), "grants": list(DEFAULT_GRANTS)}
        return self._json(status, reply)
