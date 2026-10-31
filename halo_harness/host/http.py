"""halo_harness.host.http -- the host's signed routes (Halo 3.3.7.0 R1; docs/HOST.md has the table).

    POST /host/v1/join                 {v, harness, a, ts, nonce, mac}: the six-word code authenticates it (the hub's
                                       exchange, fleet/hub_join.py); the reply adds `serves` [{name, port, addr}]
    GET  /host/v1/ping | card | catalog?window=N | profiles | events?since=&kind= | tail?n=&host= | stream
    POST /host/v1/simulate {model | size_gb, window, kv?}    POST /host/v1/route {need: {...}}
    POST /host/v1/control/* | manage/* | admin/*   403: the grant this peer does not hold (3.3.7.0 R2 gives them meaning)

Every route but `join` carries fleet/protocol.py's HMAC headers made with the peer's pair key (the 120 s window, the
replay guard): an unknown peer gets 403, a wrong key or a stale or replayed request 401. Every request writes one
audit line (host/state.audit). The routes read; nothing here loads a model or changes a server setting.
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
GETS = ("ping", "card", "catalog", "profiles", "events", "tail", "stream")
POSTS = ("simulate", "route")
GRANTED = ("control", "manage", "admin")
STREAM_EVENT_S, STREAM_RES_S, STREAM_CARD_S = 2.0, 5.0, 60.0


def grant_line(grant: str) -> str:
    return f"this peer holds no `{grant}` grant on this host: `{grant}` operations arrive in 3.3.7.0 R2"


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
                  (time.monotonic() - t0) * 1000.0)

    # ---- GET ----------------------------------------------------------------------------------
    def do_GET(self):
        self._audited(self._get)

    def _get(self) -> None:
        route = self._route()
        if route not in GETS:
            return self._json(404, {"error": "this port serves only the Halo host protocol (/host/v1)"})
        if not self._peer(b""):
            return None
        q, view = self._query(), self.svc.view
        if route == "ping":
            return self._json(200, protocol.doc(ok=True, host=self.svc.public(), you={"name": self._who,
                                                                                       "grants": list(self._grants())}))
        if route == "stream":
            return self._stream()
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

    def _frame(self, kind: str, data) -> None:
        doc = json.dumps({"type": kind, "ts": time.time(), "data": data}, ensure_ascii=False, default=str)
        self.wfile.write(f"event: {kind}\ndata: {doc}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _stream(self) -> None:
        from halo_harness.ollama_steward.resources import STORE
        from halo_harness.ollama_steward.server_events import events_path
        self.close_connection = True
        self.send_response(200)
        for k, v in (("Content-Type", "text/event-stream; charset=utf-8"), ("Cache-Control", "no-store"),
                     ("Connection", "close"), ("X-Accel-Buffering", "no")):
            self.send_header(k, v)
        self.end_headers()
        self._status = 200
        view, names = self.svc.view, [h.name for h in self.svc.view.hosts()]
        path = events_path(self.svc.home)
        size = path.stat().st_size if path.exists() else 0
        self._frame("card", view.card())
        now = time.monotonic()
        nxt = {"event": now + STREAM_EVENT_S, "res": now, "card": now + STREAM_CARD_S, "ping": now + protocol.PING_S}
        seen_t: dict = {}
        while not self.svc.stopping.is_set():
            now = time.monotonic()
            if now >= nxt["event"]:
                nxt["event"] = now + STREAM_EVENT_S
                cur = path.stat().st_size if path.exists() else 0
                if cur != size:
                    size = cur
                    for ev in view.events(since=STREAM_EVENT_S * 3)["events"]:
                        key = (ev.get("at"), ev.get("kind"), ev.get("model"))
                        if key not in seen_t:
                            seen_t[key] = 1
                            self._frame("event", ev)
            if now >= nxt["res"]:
                nxt["res"] = now + STREAM_RES_S
                for n in names:
                    s = STORE.latest(n)
                    if s and s.get("t") != seen_t.get(("res", n)):
                        seen_t[("res", n)] = s.get("t")
                        self._frame("resources", s)
            if now >= nxt["card"]:
                nxt["card"] = now + STREAM_CARD_S
                self._frame("card", view.card())
            if now >= nxt["ping"]:
                nxt["ping"] = now + protocol.PING_S
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
            if len(seen_t) > 4096:
                seen_t.clear()
            self.svc.stopping.wait(0.25)

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
        if not self._peer(raw):
            return None
        if head in GRANTED:
            return self._json(403, {"error": grant_line(head), "grant": head})
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
