"""halo_harness.remote.control_socket -- the per-session control socket
(Halo 2.0.9 round 2). The server side of the wire in `remote/protocol.py`.

Transport:

* POSIX: a Unix socket `~/.halo/run/<session_id>.ctl`, mode 0600, run dir
  0700 -- filesystem permissions are the auth. When that path is longer than
  the system allows (104 bytes on macOS: a deep home or temp folder), the
  socket is `<short per-user folder>/<hash>.ctl` and `run/<id>.ctl` is a
  0600 file naming it (3.6.0.0 R12); the registry carries the real endpoint.
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

import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import sys
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
SHUTDOWN_REPLY_BOUND_S = 2.0  # 3.6.0.4 S4-1: an ending command's end begins at most this long after it was handled
_SURROGATES = re.compile("[\ud800-\udfff]")


def run_dir() -> Path:
    d = bridge_home() / "run"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


class ControlSocketError(OSError):
    """The control socket cannot open; its message is one plain line for the person."""


def sun_path_max() -> int:
    """Bytes a Unix socket path may hold here, its NUL left out: sun_path is 108 bytes on Linux and 104 on macOS
    and the BSDs."""
    return 107 if sys.platform.startswith("linux") else 103


def path_fits(path) -> bool:
    return len(os.fsencode(str(path))) <= sun_path_max()


def short_dir() -> Path:
    """3.6.0.0 R12: a short per-user folder for a socket whose own path is too long (macOS keeps 104 bytes and its
    temp folder alone is /var/folders/xx/yyyy/T/): `$XDG_RUNTIME_DIR/halo` when that is set, else
    `/tmp/halo-<uid>`. Made 0700; refused (ControlSocketError) unless it is a real folder this user owns that no
    one else can enter."""
    xdg = os.environ.get("XDG_RUNTIME_DIR") or ""
    base = Path(xdg) / "halo" if xdg and os.path.isabs(xdg) else Path("/tmp") / f"halo-{os.getuid()}"
    try:
        base.mkdir(mode=0o700, parents=False, exist_ok=True)
        st = os.lstat(base)
    except OSError as e:
        raise ControlSocketError(f"the control socket's short folder {base} cannot be made ({e.strerror or e})") from e
    import stat as _stat
    if not _stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ControlSocketError(f"the control socket's short folder {base} is not a private folder of this user, "
                                 "so the session opens no control socket (remove it and start again)")
    return base


def socket_paths(session_id: str) -> "tuple[Path, Optional[Path]]":
    """`(bind path, pointer path or None)` for a session's Unix socket. `run/<id>.ctl` when it fits; else the
    socket is `<short_dir>/<hash>.ctl` and `run/<id>.ctl` is a small file naming it (the pointer). A short path
    that still does not fit is a ControlSocketError, one plain line."""
    named = run_dir() / f"{session_id}.ctl"
    if path_fits(named):
        return named, None
    digest = hashlib.sha256(os.fsencode(str(named))).hexdigest()[:20]
    short = short_dir() / f"{digest}.ctl"
    if not path_fits(short):
        raise ControlSocketError(f"the control socket path {short} is longer than this system's "
                                 f"{sun_path_max()} bytes, so the session opens no control socket")
    return short, named


def pointer_target(path: Path) -> Optional[Path]:
    """The socket a pointer file `run/<id>.ctl` names, or None when `path` is not a pointer."""
    try:
        if not path.is_file() or path.stat().st_size > 4096:
            return None
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return Path(text) if text and os.path.isabs(text) else None


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

    def _answer_then(self, reply: dict, then) -> None:
        """3.6.0.4 S4-1: a command that ends the session (`shutdown`, the terminal's `/exit`) begins that end once its
        answer is out, or SHUTDOWN_REPLY_BOUND_S after it was handled, or when the send fails, whichever comes first:
        a caller whose stalled subscription holds this connection's sends delays the answer, never the end. The timer
        lives for this one command and is cancelled once the send returned; `then` runs once."""
        once = threading.Lock()

        def begin() -> None:
            if once.acquire(blocking=False):
                try:
                    then()
                except Exception:  # P8: an app already closing (RuntimeError) never prints over the terminal
                    pass

        timer = threading.Timer(SHUTDOWN_REPLY_BOUND_S, begin)
        timer.name, timer.daemon = "halo-ctl-then", True
        timer.start()
        try:
            self.send(reply)
        finally:
            timer.cancel()
            begin()

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
                reply = handle_request(self.server.handle, req, self)
                then, self.then = getattr(self, "then", None), None
                if callable(then):  # 3.6.0.2 P11: `/exit` from Studio ends the terminal AFTER its answer went out
                    self._answer_then(reply, then)
                else:
                    self.send(reply)
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
        self.socket_path: Optional[Path] = None  # run/<id>.ctl: the socket itself, or the pointer to bind_path
        self.bind_path: Optional[Path] = None
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
            sock.listen(socket.SOMAXCONN)  # 3.6.0.4: a burst of probes against a lagging accept loop queues
            self.port = sock.getsockname()[1]
            self.token = secrets.token_hex(16)
            self.endpoint = f"tcp:{LOOPBACK}:{self.port}"
        else:
            d = run_dir()
            from halo_harness.remote.registry import sweep_stale_ctl
            sweep_stale_ctl(d)
            bind_path, pointer = socket_paths(self.session_id)
            self.socket_path, self.bind_path = pointer or bind_path, bind_path
            for p in (bind_path, pointer):
                try:
                    if p is not None:
                        p.unlink()
                except OSError:
                    pass
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(str(bind_path))
                sock.listen(socket.SOMAXCONN)  # at once: a bound socket that refuses connects reads as stale to a sibling's sweep
                os.chmod(bind_path, 0o600)
                if pointer is not None:
                    from halo_harness.privateio import write_private_atomic
                    write_private_atomic(pointer, str(bind_path) + "\n")
            except OSError as e:
                sock.close()
                if isinstance(e, ControlSocketError):
                    raise
                raise ControlSocketError(f"the control socket {bind_path} did not open ({e.strerror or e})") from e
            self.endpoint = f"unix:{bind_path}"
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
        for p in {self.socket_path, self.bind_path} - {None}:
            try:
                p.unlink()
            except OSError:
                pass
