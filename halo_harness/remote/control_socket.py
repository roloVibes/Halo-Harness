"""halo_harness.remote.control_socket -- the per-session control socket
(Halo 2.0.9 round 2). The server side of the wire in `remote/protocol.py`.

Transport:

* POSIX: a Unix socket `~/.halo/run/<session_id>.ctl`, mode 0600, run dir
  0700 -- filesystem permissions are the auth.
* Windows: loopback TCP (127.0.0.1, an OS-assigned port) plus a random
  16-byte hex token; a connection's first line must be `{"token": "..."}`
  within 5 s or it is closed. Nothing ever listens on a non-loopback
  address, and the token is never logged.

Many clients may connect; `subscribe` is per connection. Each connection has
its own reader thread; a subscribed connection also gets a writer thread
that drains its bounded `Subscription` (256 frames). When that queue fills
the subscription is dropped and the socket is force-closed, so a stalled
client never blocks the session or other clients.

Slots (2.0.10 review finding 5): `MAX_CONNS` (32) counts AUTHENTICATED
connections only; on Windows a connection still inside its 5 s handshake sits in
a separate pool of `MAX_PREAUTH` (16) and the oldest of them is closed when a new
one arrives, so a local process looping silent connects never starves real
clients. At most `MAX_SUBSCRIBERS` (16) connections hold a feed at once.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import socket
import threading
from pathlib import Path
from typing import Optional

from halo_harness.config.paths import bridge_home
from halo_harness.remote.handle import HandleError
from halo_harness.remote.protocol import handle_request

LOOPBACK = "127.0.0.1"
HANDSHAKE_TIMEOUT_S = 5.0
ACCEPT_POLL_S = 0.5
MAX_LINE = 1 << 20
MAX_CONNS = 32
MAX_PREAUTH = 16
MAX_SUBSCRIBERS = 16
_SURROGATES = re.compile("[\ud800-\udfff]")


def run_dir() -> Path:
    d = bridge_home() / "run"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def encode_line(obj: dict) -> bytes:
    text = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError:
        return _SURROGATES.sub("�", text).encode("utf-8")


class _Conn:
    def __init__(self, server: "ControlServer", sock: socket.socket) -> None:
        self.server, self.sock = server, sock
        self._send_lock = threading.Lock()
        self._sub = None
        self._writer: Optional[threading.Thread] = None
        self._dead = threading.Event()
        self.noted: set = set()  # phones this connection announced (protocol `note`)
        self.authed = os.name != "nt"  # POSIX: the 0600 socket is the auth; Windows: set after the token

    def send(self, obj: dict) -> bool:
        data = encode_line(obj)
        try:
            with self._send_lock:
                self.sock.sendall(data)
            return True
        except OSError:
            return False

    def force_close(self) -> None:
        self._dead.set()
        for fn in (lambda: self.sock.shutdown(socket.SHUT_RDWR), self.sock.close):
            try:
                fn()
            except OSError:
                pass

    def start_feed(self, kinds) -> None:
        self.stop_feed()
        if not self.server.reserve_feed(self):
            raise HandleError(f"too many subscribers (at most {MAX_SUBSCRIBERS} at a time)")
        sub = self.server.handle.subscribe(kinds=kinds)
        sub.on_drop = self.force_close
        self._sub = sub
        self._writer = threading.Thread(target=self._feed_loop, args=(sub,), daemon=True, name="halo-ctl-feed")
        self._writer.start()

    def stop_feed(self) -> None:
        sub, self._sub = self._sub, None
        if sub is not None:
            self.server.handle.unsubscribe(sub)

    def _feed_loop(self, sub) -> None:
        while not sub.closed.is_set() and not self._dead.is_set():
            frame = sub.get(0.25)
            if frame is not None and not self.send(frame):
                break

    def serve(self) -> None:
        rf = self.sock.makefile("rb")
        try:
            if os.name == "nt":
                if not self._handshake(rf) or not self.server.promote(self):
                    return
            while not self.server.closed.is_set() and not self._dead.is_set():
                line = rf.readline(MAX_LINE + 1)
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line.decode("utf-8", "replace"))
                except ValueError:
                    self.send({"id": None, "ok": False, "error": "invalid JSON"})
                    continue
                self.send(handle_request(self.server.handle, req, self))
        except OSError:
            pass
        finally:
            self.stop_feed()
            for peer in list(self.noted):
                try:
                    self.server.handle.set_remote_peer(peer, False)
                except Exception:
                    pass
            try:
                rf.close()
            except OSError:
                pass
            self.force_close()

    def _handshake(self, rf) -> bool:
        self.sock.settimeout(HANDSHAKE_TIMEOUT_S)
        try:
            first = rf.readline(4096)
        except OSError:
            return False
        self.sock.settimeout(None)
        try:
            hello = json.loads(first.decode("utf-8", "replace")) if first else None
        except ValueError:
            hello = None
        token = hello.get("token") if isinstance(hello, dict) else None
        if not isinstance(token, str) or not hmac.compare_digest(token, self.server.token or ""):
            if first:
                self.send({"id": None, "ok": False, "error": "bad or missing token"})
            return False
        return True


class ControlServer:
    def __init__(self, handle, *, session_id: Optional[str] = None, sndbuf: Optional[int] = None) -> None:
        self.handle = handle
        self.session_id = session_id or handle.session_id
        self.sndbuf = sndbuf  # test hook: a small send buffer makes a stalled client fill it fast
        self.closed = threading.Event()
        self.token: Optional[str] = None
        self.endpoint: Optional[str] = None
        self.socket_path: Optional[Path] = None
        self.port: Optional[int] = None
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._conns: "list[_Conn]" = []
        self._lock = threading.Lock()

    def start(self) -> "ControlServer":
        if self._sock is not None:
            return self
        if os.name == "nt":
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((LOOPBACK, 0))
            sock.listen(8)
            self.port = sock.getsockname()[1]
            self.token = secrets.token_hex(16)
            self.endpoint = f"tcp:{LOOPBACK}:{self.port}"
        else:
            d = run_dir()
            from halo_harness.remote.registry import sweep_stale_ctl
            sweep_stale_ctl(d)
            self.socket_path = d / f"{self.session_id}.ctl"
            try:
                self.socket_path.unlink()
            except OSError:
                pass
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.bind(str(self.socket_path))
            sock.listen(8)  # at once: a bound socket that refuses connects reads as stale to a sibling's sweep
            os.chmod(self.socket_path, 0o600)
            self.endpoint = f"unix:{self.socket_path}"
        self._sock = sock
        self._thread = threading.Thread(target=self._accept_loop, name="halo-ctl-accept", daemon=True)
        self._thread.start()
        return self

    def _accept_loop(self) -> None:
        while not self.closed.is_set():
            try:
                self._sock.settimeout(ACCEPT_POLL_S)
                sock, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            sock.settimeout(None)
            if self.sndbuf:
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.sndbuf)
                except OSError:
                    pass
            conn = _Conn(self, sock)
            with self._lock:
                self._conns = [c for c in self._conns if not c._dead.is_set()]
                if conn.authed and len(self._conns) >= MAX_CONNS:
                    conn.force_close()
                    continue
                if not conn.authed:  # inside the handshake: a bounded pool, oldest closed first
                    waiting = [c for c in self._conns if not c.authed]
                    while len(waiting) >= MAX_PREAUTH:
                        waiting.pop(0).force_close()
                    self._conns = [c for c in self._conns if not c._dead.is_set()]
                self._conns.append(conn)
            threading.Thread(target=conn.serve, name="halo-ctl-conn", daemon=True).start()

    def reserve_feed(self, conn: "_Conn") -> bool:
        """True when `conn` may hold a feed (it already holds one, or fewer than MAX_SUBSCRIBERS do)."""
        with self._lock:
            live = [c for c in self._conns if not c._dead.is_set() and c._sub is not None and c is not conn]
            return len(live) < MAX_SUBSCRIBERS

    def promote(self, conn: "_Conn") -> bool:
        """A Windows connection passed the token: it now counts against MAX_CONNS."""
        with self._lock:
            if sum(1 for c in self._conns if c.authed and not c._dead.is_set()) >= MAX_CONNS:
                ok = False
            else:
                conn.authed = ok = True
        if not ok:
            conn.send({"id": None, "ok": False, "error": "too many connections"})
        return ok

    def close(self) -> None:
        self.closed.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        with self._lock:
            conns, self._conns = self._conns, []
        for c in conns:
            c.force_close()
        if self.socket_path is not None:
            try:
                self.socket_path.unlink()
            except OSError:
                pass
