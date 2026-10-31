"""halo_harness.ollama_steward.host_client -- the ladder's `host` rung (Halo 3.3.7.0 R1; docs/HOST.md "The ladder").

    for_host(host, home=None) -> HostClient | None   the paired halo host that serves this Ollama host: fleet.json's
        `hosts` entries matched by the Ollama host's address and port (an entry's `serves` [{addr, port}], else its
        url's address), the way log_status._member_events matches a member's events; server_log_remote.SEAMS["host"]
        (fn(host) -> HostClient | None) is the tests' seam
    HostClient.card() | catalog(window) | profiles() | events(since, kind) | tail(n, host) | simulate(body) |
        route(need) | stream() | ping()      one signed request each (fleet/protocol.py headers, TLS pinned)
    host_reads.py: card_of / log_of / tail_of / events_of / profile_of / host_block, what hardware.py,
        log_status.py, log_tail.py, fit_evidence.py, ollama_capability.profile_for and the Hosts page read through it

The reading order is local -> host -> ssh -> member push -> api-ps: when a host answers, its card and its log win
over ssh. A host that did not answer is not asked again for DOWN_S, so a page over a dead host stays quick.
"""

from __future__ import annotations

import http.client
import json
import threading
import time
import urllib.parse
from typing import Optional

CARD_TTL_S = 15.0
PROFILES_TTL_S = 60.0
DOWN_S = 30.0
_CACHE: dict = {}  # (url, what) -> (monotonic, value)
_DOWN: dict = {}  # url -> monotonic until
_LOCAL = threading.local()  # set while a halo host answers a request: the host never reads through another host


class serving:
    """`with serving():` -- the host's request threads (host/http.py): no read in it goes through a host client."""

    def __enter__(self):
        self._was = getattr(_LOCAL, "on", False)
        _LOCAL.on = True
        return self

    def __exit__(self, *exc):
        _LOCAL.on = self._was


class HostError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


def _addr_port(url: str, default_port: int = 11434) -> "tuple[str, int]":
    try:
        u = urllib.parse.urlparse(str(url or ""))
        return (u.hostname or "").lower(), u.port or default_port
    except ValueError:
        return "", default_port


class HostClient:
    def __init__(self, entry: dict, key: bytes, member_id: str, timeout: float = 5.0) -> None:
        from halo_harness.fleet.relay import parse_url
        self.entry, self.key, self.member, self.timeout = dict(entry), key, member_id, timeout
        scheme, self.host, self.port = parse_url(entry["url"])
        self.scheme = scheme or ("https" if entry.get("tls") else "http")
        self.url = entry["url"]
        self.addr = self.host
        self.last_seen: Optional[float] = None

    @property
    def label(self) -> str:
        return f"halo host at {self.addr}"

    def _call(self, method: str, route: str, body: Optional[dict] = None) -> dict:
        from halo_harness.fleet import protocol, tls
        from halo_harness.fleet.relay import HubError, _connect
        path = "/host/v1/" + route
        raw = protocol.encode(body) if body is not None else b""
        headers = {**protocol.sign_headers(self.key, method, path, self.member, raw), "Content-Type": "application/json"}
        try:
            conn, _ = _connect(self.scheme, self.host, self.port, self.timeout, self.entry.get("fingerprint"))
            conn.request(method, path, body=raw or None, headers=headers)
            resp = conn.getresponse()
            status, data = resp.status, resp.read()
            conn.close()
        except (HubError, tls.PinMismatch) as e:
            raise HostError(str(e)) from None
        except (OSError, http.client.HTTPException) as e:
            _DOWN[self.url] = time.monotonic() + DOWN_S
            raise HostError(f"the {self.label} did not answer: {e}") from None
        try:
            got = json.loads(data.decode("utf-8") or "{}")
        except ValueError:
            got = {}
        got = got if isinstance(got, dict) else {}
        if status != 200:
            raise HostError(str(got.get("error") or f"the host answered {status}"), status)
        self.last_seen = time.time()
        return got

    def _q(self, route: str, **query) -> str:
        q = urllib.parse.urlencode({k: v for k, v in query.items() if v not in (None, "")})
        return route + (f"?{q}" if q else "")

    def ping(self) -> dict:
        return self._call("GET", "ping")

    def card(self, *, fresh: bool = False) -> dict:
        key = (self.url, "card")
        hit = _CACHE.get(key)
        if hit and not fresh and time.monotonic() - hit[0] < CARD_TTL_S:
            return hit[1]
        got = self._call("GET", "card")
        _CACHE[key] = (time.monotonic(), got)
        return got

    def catalog(self, window: int = 32768) -> dict:
        return self._call("GET", self._q("catalog", window=int(window)))

    def profiles(self) -> dict:
        return self._call("GET", "profiles")

    def events(self, since=None, kind: Optional[str] = None) -> dict:
        return self._call("GET", self._q("events", since=since, kind=kind))

    def tail(self, n: int = 200, host: str = "") -> dict:
        return self._call("GET", self._q("tail", n=int(n), host=host))

    def simulate(self, body: dict) -> dict:
        return self._call("POST", "simulate", {"v": 1, **body})

    def route(self, need: dict) -> dict:
        return self._call("POST", "route", {"v": 1, "need": need})

    def stream(self):
        """The host's SSE stream (fleet/relay_stream.Stream: `read(timeout)` returns the frames that arrived)."""
        from halo_harness.fleet import protocol
        from halo_harness.fleet.relay import _connect, format_url
        from halo_harness.fleet.relay_stream import open_stream
        path = "/host/v1/stream"
        conn, _ = _connect(self.scheme, self.host, self.port, self.timeout, self.entry.get("fingerprint"))
        host_port = format_url("http", self.host, self.port)[len("http://"):]
        return open_stream(conn.sock, host_port, path, protocol.sign_headers(self.key, "GET", path, self.member),
                           self.timeout)

    def served_row(self, port: int) -> Optional[dict]:
        """The card's row for the Ollama server on `port` there (the first one when only one is served)."""
        rows = [r for r in (self.card().get("hosts") or []) if isinstance(r, dict)]
        return next((r for r in rows if int(r.get("port") or 0) == int(port)), rows[0] if len(rows) == 1 else None)


# ---- finding the host ---------------------------------------------------------------------------------

def _matches(entry: dict, addr: str, port: int) -> bool:
    serves = [r for r in entry.get("serves") or [] if isinstance(r, dict)]
    own = _addr_port(entry.get("url") or "", 7431)[0]
    if serves:
        return any(str(r.get("addr") or own).lower() == addr and int(r.get("port") or 11434) == port for r in serves)
    return own == addr and port == 11434


def any_paired(home=None) -> bool:
    """Cheap: does fleet.json list a paired host (re-read only when the file changes)?"""
    from halo_harness.fleet import store
    p = store.path(home)
    try:
        st = p.stat()
        mt = (st.st_mtime_ns, st.st_size)
    except OSError:
        return False
    hit = _CACHE.get(("paired", str(p)))
    if hit is None or hit[0] != mt:
        hit = _CACHE[("paired", str(p))] = (mt, bool(store.hosts(home)))
    return hit[1]


def for_host(host, home=None) -> Optional[HostClient]:
    from halo_harness.ollama_steward.server_log_remote import SEAMS
    if host is None or getattr(_LOCAL, "on", False):
        return None
    if "host" in SEAMS:
        return SEAMS["host"](host)
    from halo_harness.fleet import identity, store
    from halo_harness.fleet.ollama_share import served_here
    url = str(getattr(host, "url", host) or "")
    if not url or not any_paired(home) or served_here(url):
        return None
    addr, port = _addr_port(url)
    for e in store.hosts(home):
        if e.get("state", "joined") == "joined" and _matches(e, addr, port):
            key = store.key_for(e, home)
            if key is None:
                return None
            return HostClient(e, key, identity.harness()["id"])
    return None


def _usable(c: Optional[HostClient]) -> bool:
    return c is not None and _DOWN.get(c.url, 0.0) <= time.monotonic()


def reset() -> None:
    _CACHE.clear()
    _DOWN.clear()
