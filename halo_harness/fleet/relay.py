"""halo_harness.fleet.relay -- the joiner's client: every HTTP call a joined
harness makes toward a hub (Halo 3.0.5.0 "Fleet" round R2). relay_runtime.py
runs it; `halo fleet join | leave | status` call it directly.

* `join(url, code, harness)`: the pairing round trip (pair_kex.py). Over
  https the hub's certificate fingerprint must be the one the hub vouches
  for inside its code-authenticated reply (and `--fingerprint`, when given).
* `HubLink(entry, key, member_id)`: signed requests (protocol.py) on one
  kept-alive connection, re-signed on a retry, TLS pinned to the stored
  fingerprint; `open_stream(link)` the SSE stream of commands, read with
  short timeouts (relay_stream.py) so the relay thread never blocks on it.

Offline mode (`--offline`, `network.offline`) refuses every call here
before a socket opens: the relay stops, `join` says why.
"""

from __future__ import annotations

import hmac
import http.client
import json
import secrets
import socket
import threading
import time
from typing import Optional

from halo_harness.fleet import identity, pair_kex, protocol, tls
from halo_harness.fleet.relay_stream import Stream, StreamError, open_stream


class HubError(Exception):
    def __init__(self, message: str, status: int = 0, kicked: bool = False) -> None:
        super().__init__(message)
        self.status, self.kicked = status, kicked


def parse_url(text: str) -> "tuple[Optional[str], str, int]":
    """`(scheme or None, host, port)` from `host:port`, `host` or `http(s)://host:port`."""
    raw = (text or "").strip().rstrip("/")
    scheme = None
    if "://" in raw:
        scheme, _, raw = raw.partition("://")
        scheme = scheme.lower()
        if scheme not in ("http", "https"):
            raise ValueError(f"a hub address is host:port or an http(s) URL, got {text!r}")
        raw = raw.split("/", 1)[0]
    if raw.startswith("["):
        host, _, rest = raw[1:].partition("]")
        port_s = rest[1:] if rest.startswith(":") else ""
    else:
        host, _, port_s = raw.rpartition(":") if raw.count(":") == 1 else (raw, "", "")
    if not host:
        raise ValueError(f"no host in {text!r}")
    if port_s and not port_s.isdigit():
        raise ValueError(f"bad port in {text!r}")
    return scheme, host, int(port_s) if port_s else identity.DEFAULT_PORT


def format_url(scheme: str, host: str, port: int) -> str:
    return f"{scheme}://{'[' + host + ']' if ':' in host else host}:{port}"


def _check_offline() -> None:
    if identity.offline():
        raise HubError("offline mode is on (--offline or network.offline): the fleet relay does not connect")


def _connect(scheme: str, host: str, port: int, timeout: float, fingerprint: Optional[str] = None):
    """`(connection, the server's fingerprint or None)`."""
    _check_offline()
    if scheme == "https":
        conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=tls.client_context())
        conn.connect()
        return conn, tls.check_pin(conn.sock, fingerprint)
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    conn.connect()
    return conn, None


def detect_scheme(host: str, port: int, timeout: float = 5.0) -> str:
    """`http` when the hub answers a plain HTTP request (an unsigned ping it
    refuses), `https` when it drops it (a TLS hub reads no plain text)."""
    _check_offline()
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", protocol.PREFIX + "/ping")
        conn.getresponse().read()
        return "http"
    except (ConnectionRefusedError, socket.timeout, TimeoutError, socket.gaierror) as e:
        raise HubError(f"cannot reach the hub at {host}:{port}: {e}") from None
    except (OSError, http.client.HTTPException):
        return "https"
    finally:
        conn.close()


def _decode(status: int, data: bytes) -> dict:
    try:
        body = json.loads(data.decode("utf-8") or "{}")
    except ValueError:
        body = {}
    body = body if isinstance(body, dict) else {}
    if status != 200:
        raise HubError(str(body.get("error") or f"the hub answered {status}"), status, bool(body.get("kicked")))
    return body


def join(url: str, code: str, harness: dict, *, share: Optional[str] = None, allow_control: Optional[str] = None,
         fingerprint: Optional[str] = None, timeout: float = 10.0) -> dict:
    scheme, host, port = parse_url(url)
    scheme = scheme or detect_scheme(host, port, timeout)
    ckey = pair_kex.code_key(code)
    a_secret, a = pair_kex.keypair()
    ts, nonce = f"{time.time():.3f}", secrets.token_hex(16)
    body = protocol.doc(harness=harness, share=share, allow_control=allow_control, a=a, ts=ts, nonce=nonce,
                        mac=pair_kex.mac(ckey, "join", harness["id"], a, ts, nonce))
    try:
        conn, seen = _connect(scheme, host, port, timeout, fingerprint)
        conn.request("POST", protocol.PREFIX + "/join", body=protocol.encode(body),
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        status, data = resp.status, resp.read()
        conn.close()
    except tls.PinMismatch as e:
        raise HubError(str(e)) from None
    except (OSError, http.client.HTTPException) as e:
        raise HubError(f"cannot reach the hub at {host}:{port}: {e}") from None
    reply = _decode(status, data)
    hub = reply.get("hub") if isinstance(reply.get("hub"), dict) else {}
    b, fp = str(reply.get("b") or ""), str(hub.get("fingerprint") or "")
    if not hmac.compare_digest(str(reply.get("mac") or ""), pair_kex.mac(ckey, "joined", a, b, hub.get("id"), fp)):
        raise HubError("the hub's answer does not prove it knows the code; not joined")
    if scheme == "https" and fp.lower() != (seen or "").lower():
        raise HubError("the certificate the hub showed is not the one it vouched for; not joined")
    return {"url": format_url(scheme, host, port), "name": hub.get("name"), "hub_id": hub.get("id"),
            "fingerprint": fp or None, "tls": scheme == "https", "member_name": reply.get("member_name"),
            "hub_version": hub.get("version"), "key": pair_kex.pair_key(a_secret, b, ckey, a, b)}


class HubLink:
    def __init__(self, entry: dict, key: bytes, member_id: str, timeout: float = 5.0) -> None:
        scheme, self.host, self.port = parse_url(entry["url"])
        self.scheme = scheme or ("https" if entry.get("tls") else "http")
        self.fingerprint = entry.get("fingerprint")
        self.key, self.member, self.timeout = key, member_id, timeout
        self._conn = None
        self._lock = threading.Lock()  # the relay thread and its command workers share the connection

    def _close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def request(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        with self._lock:
            return self._request(method, path, protocol.encode(body) if body is not None else b"")

    def _request(self, method: str, path: str, raw: bytes) -> dict:
        for attempt in (0, 1):
            headers = {**protocol.sign_headers(self.key, method, path, self.member, raw),
                       "Content-Type": "application/json"}
            try:
                if self._conn is None:
                    self._conn, _ = _connect(self.scheme, self.host, self.port, self.timeout, self.fingerprint)
                self._conn.request(method, path, body=raw or None, headers=headers)
                resp = self._conn.getresponse()
                status, data = resp.status, resp.read()
                if resp.will_close:
                    self._close()
                return _decode(status, data)
            except HubError:
                raise
            except (OSError, http.client.HTTPException) as e:
                self._close()
                if attempt or isinstance(e, tls.PinMismatch):
                    raise HubError(f"{self.host}:{self.port}: {e}") from None
        raise HubError("unreachable")

    def open_stream(self, link_id: str) -> Stream:
        """The signed SSE stream of this link's commands (relay_stream.py reads it)."""
        path = f"{protocol.PREFIX}/stream?link={link_id}"
        host_port = format_url("http", self.host, self.port)[len("http://"):]
        try:
            conn, _ = _connect(self.scheme, self.host, self.port, self.timeout, self.fingerprint)
            return open_stream(conn.sock, host_port, path, protocol.sign_headers(self.key, "GET", path, self.member),
                               self.timeout)
        except StreamError as e:
            if e.status:
                _decode(e.status, e.body)
            raise HubError(f"{self.host}:{self.port}: {e}") from None
        except (OSError, http.client.HTTPException) as e:
            raise HubError(f"{self.host}:{self.port}: {e}") from None

    def close(self) -> None:
        self._close()
