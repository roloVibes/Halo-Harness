"""halo_harness.remote.signal_transport -- the signal-cli JSON-RPC client
(Halo 2.0.9 round 3).

Default transport: a spawned `signal-cli -a ACCOUNT --trust-new-identities
never --scrub-log -d <remote>/signal-cli jsonRpc ...` child talked to over
stdio, newline JSON-RPC 2.0 both ways (no listener, no port, no socket
file). Optional: a client of a separately running `daemon --socket` (POSIX)
or `daemon --tcp 127.0.0.1:PORT`, for a service-manager install where
signal-cli outlives the bridge. Settings come from `signal.json`
(signal_config.py).

Everything the child says arrives through ONE sink callable set with
`set_sink(fn)`; items are plain dicts:

    {"kind": "envelope", "envelope": {...}, "exception": {...}|None, "account": str|None}
    {"kind": "notice",   "name": "connected"|"disconnected"|"rate_limited"|
                                   "subscribe_failed", ...}

The sink runs on the reader thread and must only enqueue. A link that ends
(child exit, EOF, a `-3` reply) is respawned/reconnected with backoff; the
bridge never has to restart. Nothing the child prints on stderr is kept, and
no message text is logged or stored here.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.remote import signal_errors as E
from halo_harness.remote.signal_calls import SignalCalls
from halo_harness.remote.signal_link import Link, open_link
from halo_harness.remote.signal_typing import TypingKeeper

BACKOFF = (1.0, 2.0, 4.0, 8.0, 15.0, 30.0)
STABLE_S = 10.0
REQUEST_TIMEOUT_S = 30.0
SUBSCRIBE_TRIES = 4
PERMANENT_CODES = (-32601, -32602)  # method not found / invalid params: retrying cannot help


class SignalTransport(SignalCalls):
    def __init__(self, cfg: dict, *, backoff=BACKOFF, typing_interval: float = 10.0,
                 request_timeout: float = REQUEST_TIMEOUT_S, popen=subprocess.Popen) -> None:
        self.cfg = cfg
        self.account = str(cfg.get("account") or "")
        self.linked = cfg.get("identity_model") == "linked"
        self.own_aci = str(cfg.get("own_aci") or "")
        self.data_dir = Path(cfg["data_dir"])
        self.backoff = tuple(backoff) or (1.0,)
        self.request_timeout = request_timeout
        self._popen = popen
        self._sink: Callable[[dict], None] = lambda item: None
        self._ids = itertools.count(1)
        self._pending: dict = {}
        self._plock = threading.Lock()
        self._link: Optional[Link] = None
        self._connected = threading.Event()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.paused_until = 0.0
        self.captcha_token = ""
        self.connects = 0
        self.backoffs: list = []
        self.typing = TypingKeeper(self, typing_interval)

    # ---- lifecycle ---------------------------------------------------------
    def set_sink(self, fn: Callable[[dict], None]) -> None:
        self._sink = fn

    def start(self) -> "SignalTransport":
        if self._thread is None:
            self._thread = threading.Thread(target=self._supervise, name="halo-signal-link", daemon=True)
            self._thread.start()
        return self

    def wait_connected(self, timeout: float = 10.0) -> bool:
        return self._connected.wait(timeout)

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def stop(self) -> None:
        self._stop.set()
        self.typing.stop_all()
        link = self._link
        if link is not None:
            link.interrupt()
        if self._thread is not None:
            self._thread.join(3.0)

    def _notice(self, name: str, **kw) -> None:
        self._sink({"kind": "notice", "name": name, **kw})

    # ---- connection --------------------------------------------------------
    def _open(self) -> Link:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return open_link(self.cfg, self._popen)

    def _supervise(self) -> None:
        idx = 0
        while not self._stop.is_set():
            try:
                link = self._open()
            except Exception:
                link = None
            if link is not None:
                self._link = link
                self.connects += 1
                self._connected.set()
                self._notice("connected")
                if (self.cfg.get("receive_mode") or "manual") == "manual":
                    threading.Thread(target=self._subscribe, daemon=True, name="halo-signal-sub").start()
                self._read_loop(link)
                self._drop(link)
                if time.monotonic() - link.born >= STABLE_S:
                    idx = 0
            if self._stop.is_set():
                break
            delay = self.backoff[min(idx, len(self.backoff) - 1)]
            idx += 1
            self.backoffs.append(delay)
            if self._stop.wait(delay):
                break

    def _drop(self, link: Link) -> None:
        link.close()
        self._connected.clear()
        if self._link is link:
            self._link = None
        with self._plock:
            waiting = list(self._pending.values())
            self._pending.clear()
        for slot in waiting:
            slot["response"] = {"error": {"code": -3, "message": "signal-cli link closed"}}
            slot["event"].set()
        if not self._stop.is_set():
            self._notice("disconnected")

    def _subscribe(self) -> None:
        """subscribeReceive for the link just opened, retried on the BACKOFF
        schedule; a permanent rejection (or the bound) is reported once per
        link as `subscribe_failed`, and no reply at all drops the link so the
        supervisor reconnects. A daemon client names the account, since a
        multi-account daemon refuses the call without it."""
        link = self._link
        params = {} if (self.cfg.get("transport") or "stdio") == "stdio" else {"account": self.account}
        err: Optional[E.SignalError] = None
        for attempt in range(SUBSCRIBE_TRIES):
            if self._stop.is_set() or link is None or self._link is not link:
                return
            try:
                self.request("subscribeReceive", params)
                return
            except E.SignalError as e:
                err = e
            if self._link is not link or not self._connected.is_set():
                return  # the link went away; the next one subscribes again
            if isinstance(err, E.IOFailure):  # no reply: an unsubscribed link is worse than a reconnect
                if str(err.message).startswith("no reply"):
                    self._notice("subscribe_failed", code=err.code, message=err.message)
                link.interrupt()
                return
            if err.code in PERMANENT_CODES or self._stop.wait(self.backoff[min(attempt, len(self.backoff) - 1)]):
                break
        if err is not None and not self._stop.is_set() and self._link is link:
            self._notice("subscribe_failed", code=err.code, message=err.message)

    # ---- reading -----------------------------------------------------------
    def _read_loop(self, link: Link) -> None:
        while not self._stop.is_set():
            try:
                raw = link.rfile.readline()
            except (OSError, ValueError):
                return
            if not raw:
                return
            try:
                msg = json.loads(raw.decode("utf-8"))
            except ValueError:
                continue
            if isinstance(msg, dict):
                self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        if "method" in msg and "id" not in msg:
            if msg["method"] == "receive" and isinstance(msg.get("params"), dict):
                p = msg["params"]
                if isinstance(p.get("result"), dict) and "subscription" in p:
                    p = p["result"]
                env = p.get("envelope")
                if isinstance(env, dict) or isinstance(p.get("exception"), dict):
                    self._sink({"kind": "envelope", "envelope": env if isinstance(env, dict) else {},
                                "exception": p.get("exception") if isinstance(p.get("exception"), dict) else None,
                                "account": p.get("account")})
            return
        with self._plock:
            slot = self._pending.pop(msg.get("id"), None)
        if slot is not None:
            slot["response"] = msg
            slot["event"].set()

    # ---- requests ------------------------------------------------------------
    def request(self, method: str, params: Optional[dict] = None, timeout: Optional[float] = None):
        link = self._link
        if link is None or not self._connected.is_set():
            raise E.IOFailure("signal-cli is not connected")
        rid = next(self._ids)
        slot = {"event": threading.Event(), "response": None}
        with self._plock:
            self._pending[rid] = slot
        try:
            link.write({"jsonrpc": "2.0", "method": method, "params": params or {}, "id": rid})
        except (OSError, ValueError):
            with self._plock:
                self._pending.pop(rid, None)
            link.interrupt()
            raise E.IOFailure("could not write to signal-cli") from None
        if not slot["event"].wait(timeout if timeout is not None else self.request_timeout):
            with self._plock:
                self._pending.pop(rid, None)
            raise E.IOFailure(f"no reply to {method}")
        resp = slot["response"] or {}
        if "error" in resp:
            exc = E.error_from(resp["error"])
            if isinstance(exc, E.IOFailure):
                link.interrupt()  # the supervisor respawns/reconnects
            elif isinstance(exc, E.RateLimited):
                self.paused_until = time.monotonic() + exc.retry_after
                self.captcha_token = exc.token
                self._notice("rate_limited", retry_after=exc.retry_after, token=exc.token)
            raise exc
        return resp.get("result")

    def rate_limited(self) -> float:
        """Seconds left of a `-5` pause (0 when sending is open)."""
        return max(0.0, self.paused_until - time.monotonic())
