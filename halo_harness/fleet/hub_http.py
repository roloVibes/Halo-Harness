"""halo_harness.fleet.hub_http -- the routes of the hub port (Halo 3.0.5.0
"Fleet" round R2). Only `/fleet/v1/...` is served here (protocol.py has the
shapes); Studio's loopback API never answers on this port, and nothing here
reaches it. Every route but `join` (the code authenticates it) and
`local/state` (loopback peer plus the hub's own admin token) checks the
request's HMAC signature, its clock and its nonce before reading anything;
a removed member gets 403 with `kicked: true`.
"""

from __future__ import annotations

import hmac
import http.server
import json
import os
import sys
import time
from urllib.parse import parse_qs, urlsplit

from halo_harness.fleet import protocol
from halo_harness.fleet.hub_join import handle_join

LOOPBACK = ("127.0.0.1", "::1", "::ffff:127.0.0.1")
MAX_BODY = 4_000_000


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "HaloFleet/1"
    timeout = 30

    def log_message(self, fmt, *args):  # quiet unless HALO_FLEET_LOG is set
        if os.environ.get("HALO_FLEET_LOG"):
            sys.stderr.write("fleet hub %s - %s\n" % (self.address_string(), fmt % args))

    @property
    def hub(self):
        return self.server.hub

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

    def _raw_body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise ValueError("body too large")
        return self.rfile.read(n) if n > 0 else b""

    def _signed(self, raw: bytes):
        """The member id, or None after answering 401/403."""
        state = self.hub.state
        hid, why = protocol.check_headers(self.headers, self.command, self.path, raw, state.key_for, self.hub.guard)
        if hid:
            return hid
        if why == "unknown member":
            claimed = str(self.headers.get(protocol.H_MEMBER) or "")
            self._json(403, {"error": "not a member of this hub (kicked, left, or never joined)",
                             "kicked": claimed in state.pairing.kicked()})
        else:
            self._json(401, {"error": f"request refused: {why}"})
        return None

    def _route(self) -> str:
        path = urlsplit(self.path).path
        return path[len(protocol.PREFIX) + 1:] if path.startswith(protocol.PREFIX + "/") else ""

    # ---- GET ------------------------------------------------------------------
    def do_GET(self):
        route = self._route()
        if route == "local/state":
            return self._local_state()
        if route == "local/capabilities":  # 3.0.6.0 R6: every harness's catalog, for this machine's Studio and CLI
            return self._local_capabilities()
        if route not in ("stream", "ping"):
            return self._json(404, {"error": "this port serves only the Halo fleet protocol (/fleet/v1)"})
        hid = self._signed(b"")
        if not hid:
            return None
        if route == "ping":
            return self._json(200, protocol.doc(ok=True, hub=self.hub.state.hub_public(), you=self.hub.state.you(hid)))
        link_id = (parse_qs(urlsplit(self.path).query).get("link") or [""])[-1]
        return self._stream(hid, link_id)

    def _admin(self) -> bool:
        token = str(self.headers.get(protocol.H_ADMIN) or "")
        if self.client_address[0] not in LOOPBACK or not token or not hmac.compare_digest(token, self.hub.admin_token):
            self._json(403, {"error": "the hub's local routes answer only its own machine's halo"})
            return False
        return True

    def _local_state(self):
        return self._json(200, self.hub.state.view()) if self._admin() else None

    def _local_capabilities(self):
        if not self._admin():
            return None
        q = parse_qs(urlsplit(self.path).query)
        hid, refresh = (q.get("harness") or [""])[-1], (q.get("refresh") or [""])[-1] in ("1", "true")
        if hid and refresh:
            status, got = self.hub.state.caps.fetch_now(hid)
            if status != 200:
                return self._json(status, got)
        return self._json(200, {"harnesses": self.hub.state.caps.entries()})

    def _local_command(self):
        """`{harness, session_id, cmd, fields, wait_s}` from this machine's `halo fleet` table."""
        if not self._admin():
            return None
        try:
            body = protocol.decode(self._raw_body())
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        from halo_harness.fleet.identity import fleet_name
        status, out = self.hub.state.commands.send(
            str(body.get("harness") or ""), str(body.get("session_id") or ""), str(body.get("cmd") or ""),
            body.get("fields") if isinstance(body.get("fields"), dict) else {}, by=fleet_name(self.hub.home),
            wait_s=float(body.get("wait_s") or 5.0))
        return self._json(status, out)

    def _write_doc(self, doc: dict, member=None, link=None) -> None:
        """One SSE event; a queued doc is signed here, numbered in the order this stream writes it."""
        if member is not None:
            doc = protocol.sign_down(member.key, member.id, link.id, {**doc, "seq": link.next_seq(), "ts": time.time()})
        data = json.dumps(doc, ensure_ascii=False, default=str)
        self.wfile.write(f"event: {doc.get('type', 'message')}\ndata: {data}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _stream(self, hid: str, link_id: str):
        state = self.hub.state
        if not link_id:
            return self._json(400, {"error": "stream needs ?link=<id>"})
        link, gen = state.stream_open(hid, link_id)
        member = state.members.get(hid)
        if link is None or member is None or member.key is None:
            if link is not None:
                state.stream_closed(link)
            return self._json(403, {"error": "not a member of this hub"})
        self.close_connection = True
        try:
            self.send_response(200)
            for k, v in (("Content-Type", "text/event-stream; charset=utf-8"), ("Cache-Control", "no-store"),
                         ("Connection", "close"), ("X-Accel-Buffering", "no")):
                self.send_header(k, v)
            self.end_headers()
            self._write_doc(protocol.sign_down(member.key, hid, link.id, {
                "type": "hello", "seq": link.next_seq(), "ts": time.time(), "hub": state.hub_public(),
                "member_name": member.name}))
            next_ping = time.monotonic() + protocol.PING_S
            while not self.hub.stopping.is_set() and link.gen == gen:
                try:
                    doc = link.queue.get(timeout=0.5)
                except Exception:
                    doc = None
                if doc is not None and link.gen != gen:  # a newer stream took over: hand the doc on
                    link.push(doc)
                    break
                if doc is not None:
                    try:
                        self._write_doc(doc, member, link)
                    except OSError:
                        link.push(doc)  # this link's next stream sends it
                        raise
                    if doc.get("type") == "kicked":
                        break
                    next_ping = time.monotonic() + protocol.PING_S
                elif link.closed.is_set():
                    break
                elif time.monotonic() >= next_ping:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    next_ping = time.monotonic() + protocol.PING_S
                state.touch(hid, link.id)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            state.stream_closed(link)
        return None

    # ---- POST -----------------------------------------------------------------
    def do_POST(self):
        route = self._route()
        if route == "local/command":
            return self._local_command()
        if route in ("mission_files", "local/mission"):  # 3.0.6.0 R7: fleet/hub_mission.py
            from halo_harness.fleet.hub_mission import serve
            return serve(self, route)
        if route in ("recall", "local/recall", "local/coach-library"):  # 3.1.2.0 R3 recall; 3.1.6.0 R3 the coach library
            from halo_harness.fleet.hub_recall import serve as recall
            return recall(self, route)
        if route not in ("join", "announce", "frames", "reply", "leave"):
            return self._json(404, {"error": "this port serves only the Halo fleet protocol (/fleet/v1)"})
        try:
            raw = self._raw_body()
        except ValueError as e:
            return self._json(413, {"error": str(e)})
        state = self.hub.state
        if route == "join":
            try:
                body = protocol.decode(raw)
            except ValueError as e:
                return self._json(400, {"error": f"bad join request: {e}"})
            status, reply = handle_join(state, body, self.client_address[0], self.hub.gate)
            return self._json(status, reply)
        hid = self._signed(raw)
        if not hid:
            return None
        try:
            body = protocol.decode(raw)
        except ValueError as e:
            return self._json(400, {"error": f"bad request: {e}"})
        if route == "announce":
            got = state.announce(hid, body)
        elif route == "frames":
            n = state.frames(hid, body)
            got = None if n is None else {"ok": True, "accepted": n}
        elif route == "reply":
            got = {"ok": state.commands.reply(hid, body)}
        else:
            state.leave(hid)
            got = {"ok": True, "left": True}
        if got is None:
            return self._json(400, {"error": "a link id is required"})
        return self._json(200, protocol.doc(**got))
