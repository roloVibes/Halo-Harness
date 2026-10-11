"""halo_harness.remote.client -- a small client for the control socket.

Used by the registry's connect probe, `halo remote sessions`, the tests and
(round 3) the Signal bridge. An endpoint is the string the server publishes:
`unix:<path>` (POSIX) or `tcp:127.0.0.1:<port>` (Windows; needs the token).
"""

from __future__ import annotations

import json
import socket
import time
from typing import Optional

PROBE_TIMEOUT_S = 0.3
NL = bytes([10])


def parse_endpoint(endpoint: str) -> tuple:
    """`("unix", path)` or `("tcp", host, port)`; ValueError on anything else."""
    if isinstance(endpoint, str) and endpoint.startswith("unix:"):
        return ("unix", endpoint[5:])
    if isinstance(endpoint, str) and endpoint.startswith("tcp:"):
        host, _, port = endpoint[4:].rpartition(":")
        if host and port.isdigit():
            return ("tcp", host, int(port))
    raise ValueError(f"unrecognised control endpoint: {endpoint!r}")


def open_socket(endpoint: str, timeout: float = 5.0) -> socket.socket:
    kind, *rest = parse_endpoint(endpoint)
    if kind == "unix":
        if not hasattr(socket, "AF_UNIX"):
            raise OSError("Unix sockets are not available on this platform")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        target = rest[0]
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target = (rest[0], rest[1])
    sock.settimeout(timeout)
    try:
        sock.connect(target)
    except OSError:
        sock.close()
        raise
    return sock


def probe(endpoint: str, timeout: float = PROBE_TIMEOUT_S) -> bool:
    """True when something accepts a connection at `endpoint`."""
    try:
        sock = open_socket(endpoint, timeout)
    except (OSError, ValueError):
        return False
    sock.close()
    return True


class ControlClient:
    def __init__(self, endpoint: str, token: Optional[str] = None, timeout: float = 5.0) -> None:
        self.sock = open_socket(endpoint, timeout)
        self.timeout = timeout
        self._buf = b""
        self._next_id = 0
        self.events: list = []  # event frames read while waiting for a response
        if token is not None:
            self.sock.sendall((json.dumps({"token": token}) + "\n").encode("utf-8"))

    def _read(self, timeout: float) -> Optional[dict]:
        """The next JSON line, or None when `timeout` passes first (own
        buffering: a socket timeout never corrupts a buffered reader)."""
        deadline = time.monotonic() + timeout
        while NL not in self._buf:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            self.sock.settimeout(remaining)
            try:
                chunk = self.sock.recv(65536)
            except (socket.timeout, TimeoutError):
                return None
            if not chunk:
                raise ConnectionError("control socket closed")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(NL)
        return json.loads(line.decode("utf-8"))

    def call(self, cmd: str, **fields) -> dict:
        """Send one request; return its response dict (`ok`/`result`/`error`).
        Event frames that arrive first are kept in `self.events`."""
        self._next_id += 1
        rid = self._next_id
        self.sock.settimeout(self.timeout)
        self.sock.sendall((json.dumps({"id": rid, "cmd": cmd, **fields}) + "\n").encode("utf-8"))
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            msg = self._read(max(0.05, deadline - time.monotonic()))
            if msg is None:
                break
            if "event" in msg:
                self.events.append(msg)
            elif msg.get("id") in (rid, None):
                return msg
        raise TimeoutError(f"no response to {cmd!r}")

    def next_event(self, timeout: float = 2.0) -> Optional[dict]:
        if self.events:
            return self.events.pop(0)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self._read(max(0.05, deadline - time.monotonic()))
            if msg is not None and "event" in msg:
                return msg
        return None

    def wait_event(self, kind: str, timeout: float = 5.0) -> Optional[dict]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ev = self.next_event(max(0.05, deadline - time.monotonic()))
            if ev is not None and ev["event"] == kind:
                return ev
        return None

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def default_token_for(entry: dict) -> Optional[str]:
    """The token for a registry entry: its stored `token` (Windows loopback)
    or None (POSIX socket; the file mode is the auth)."""
    tok = entry.get("token") if isinstance(entry, dict) else None
    return tok if isinstance(tok, str) and tok else None
