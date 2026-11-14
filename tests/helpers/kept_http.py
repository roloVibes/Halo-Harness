"""tests.helpers.kept_http -- the rigs' calls to a local server keep their connection (3.6.0.0 R3).

Why: on Windows a client that closes a loopback connection holds its local port in TIME_WAIT for about two minutes,
and the dynamic range is 16,384 ports (some reserved). A rig that opened a connection per call -- a poll every 50 ms
of the session's agent tree, an API call per step -- spent hundreds of ports a module (test_studio_session_live: about
400 in 12 s), and four Chrome shards beside the fast ones ran the range dry: `OSError: [WinError 10048] Only one usage
of each socket address` raised from the rig's own connect, red beside the others and green alone.

    request(port, method, path, body_bytes, headers, timeout) -> (status, bytes, headers)
        one HTTP/1.1 connection per thread and port, kept between calls; a connection the server closed (an error
        status closes it, an idle one times out) is opened again once, before anything was sent twice
    connect(open_fn, seconds=5.0)
        `open_fn()` tried again for a short, bounded time when the connect itself finds no free local port
        (WinError 10048 / EADDRINUSE, EADDRNOTAVAIL on Linux): a port comes back as TIME_WAIT entries expire
    Kept(make)                     a kept client object per thread (the session's control socket), made again on error
"""

from __future__ import annotations

import errno
import http.client
import threading
import time

NO_PORT = {errno.EADDRINUSE, errno.EADDRNOTAVAIL, 10048, 10049}
_STALE = (http.client.RemoteDisconnected, http.client.BadStatusLine, ConnectionResetError, ConnectionAbortedError,
          BrokenPipeError)
_local = threading.local()


def _no_port(e: OSError) -> bool:
    return getattr(e, "winerror", None) in NO_PORT or e.errno in NO_PORT


def connect(open_fn, seconds: float = 5.0):
    """`open_fn()`, again while the connect finds no free local port, for at most `seconds` (no test waits longer
    for its own value: this only covers the moment the host's port range is empty)."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            return open_fn()
        except OSError as e:
            if not _no_port(e) or time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def _conns() -> dict:
    got = getattr(_local, "conns", None)
    if got is None:
        got = _local.conns = {}
    return got


def _open(port: int, timeout: float) -> http.client.HTTPConnection:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
    connect(conn.connect)
    return conn


def request(port: int, method: str, path: str, body: "bytes | None", headers: dict, timeout: float = 30.0):
    """(status, body bytes, headers) over this thread's kept connection to `port`."""
    pool = _conns()
    for attempt in (0, 1):
        conn = pool.get(port)
        fresh = conn is None
        if fresh:
            conn = pool[port] = _open(port, timeout)
        conn.timeout = timeout
        if conn.sock is not None:
            conn.sock.settimeout(timeout)
        try:
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except _STALE:
            conn.close()
            pool.pop(port, None)
            if fresh or attempt:  # a new connection that failed is a real failure, not a stale one
                raise
            continue
        except Exception:
            conn.close()
            pool.pop(port, None)
            raise
        if resp.will_close:
            conn.close()
            pool.pop(port, None)
        return resp.status, data, dict(resp.getheaders())
    raise ConnectionError("unreachable")


class Kept:
    """One client per thread from `make()` (made again after an error), so a poll reuses one socket."""

    def __init__(self, make) -> None:
        self._make = make
        self._local = threading.local()
        self._all: list = []
        self._lock = threading.Lock()

    def call(self, fn):
        c = getattr(self._local, "c", None)
        if c is None:
            c = self._local.c = connect(self._make)
            with self._lock:
                self._all.append(c)
        try:
            return fn(c)
        except Exception:
            self.drop()
            raise

    def drop(self) -> None:
        c = getattr(self._local, "c", None)
        self._local.c = None
        if c is not None:
            try:
                c.close()
            except Exception:
                pass

    def close(self) -> None:
        with self._lock:
            got, self._all = self._all, []
        for c in got:
            try:
                c.close()
            except Exception:
                pass
