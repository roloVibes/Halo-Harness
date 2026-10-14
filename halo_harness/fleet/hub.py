"""halo_harness.fleet.hub -- the hub listener (Halo 3.0.5.0 "Fleet" round R2).

`HubServer(home, port=7430, bind="0.0.0.0", name=...)` serves the fleet
protocol (hub_http.py) on its own LAN port: plain HTTP + SSE with every
request HMAC-signed, inside TLS when the hub has a certificate (tls.py:
generated on first serve when `cryptography` is installed; `tls=False`, or
`serve --no-tls`, keeps it HMAC-only). It runs inside Studio's process
(`halo studio --fleet`, or `halo fleet serve` while Studio runs) or on its
own (`halo fleet serve`). It never serves Studio's loopback API. Offline
mode (`--offline`, `network.offline`) refuses to start it.

While it runs, `<home>/fleet/hub/serve.json` (0600) says where: `{pid, port,
bind, tls, fingerprint, name, admin_token, started}`; `running_call(home,
...)` sends that hub one loopback request with the admin token (the one raw
client call in this file): `running_view` is its merged view, and the
terminal table's commands go through `local/command`, for `halo fleet
status | members` and the table on the hub's machine when the hub runs in
another process.
"""

from __future__ import annotations

import http.client
import http.server
import json
import os
import secrets
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import identity, protocol, tls
from halo_harness.fleet.hub_http import Handler
from halo_harness.fleet.hub_join import JoinGate
from halo_harness.fleet.hub_state import HubState
from halo_harness.fleet.pairing import HubPairing, hub_dir

SERVE_FILE = "serve.json"
TICK_S = 1.0


class FleetOffline(RuntimeError):
    pass


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, addr, hub, ssl_ctx) -> None:
        self.hub, self.ssl_ctx = hub, ssl_ctx
        super().__init__(addr, Handler)

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def finish_request(self, request, client_address):
        if self.ssl_ctx is not None:  # the handshake runs on the request's own thread, never the accept loop
            request.settimeout(10)
            try:
                request = self.ssl_ctx.wrap_socket(request, server_side=True)
            except OSError:
                return
        super().finish_request(request, client_address)


class HubServer:
    def __init__(self, home=None, *, port: Optional[int] = None, bind: str = "0.0.0.0", name: Optional[str] = None,
                 tls_on: Optional[bool] = None, local_view: Optional[Callable] = None, record: bool = True) -> None:
        self.home = Path(home) if home is not None else identity.home()
        self.port = identity.hub_port(self.home) if port is None else int(port)
        self.bind = bind or "0.0.0.0"
        self.name = (name or identity.fleet_name(self.home)).strip()[:64]
        self.tls_on = tls_on
        self.record = record
        self.admin_token = secrets.token_urlsafe(24)
        self.guard = protocol.ReplayGuard()
        self.gate = JoinGate()
        self.stopping = threading.Event()
        self.pairing = HubPairing(self.home)
        self.state = HubState(self.home, name=self.name, identity=identity.harness(self.home),
                              local_view=local_view, pairing=self.pairing)
        self.server: Optional[_Server] = None
        self.fingerprint: Optional[str] = None

    def start(self) -> "HubServer":
        if identity.offline():
            raise FleetOffline("offline mode is on (--offline or network.offline): the fleet hub listens on the "
                               "LAN, so it does not start; `/offline off` or drop --offline first")
        ctx = None
        if self.tls_on is not False:
            got = tls.ensure_cert(hub_dir(self.home), self.name)
            if got is None and self.tls_on:
                raise RuntimeError("TLS needs the `cryptography` package (pip install 'halo-harness[fleet]')")
            if got is not None:
                ctx, self.fingerprint = tls.server_context(got[0], got[1]), got[2]
        self.server = _Server((self.bind, self.port), self, ctx)
        self.port = self.server.server_address[1]
        self.state.serving = {"port": self.port, "bind": self.bind, "tls": ctx is not None,
                              "fingerprint": self.fingerprint, "url": self.url()}
        threading.Thread(target=self.server.serve_forever, name="halo-fleet-hub", daemon=True).start()
        threading.Thread(target=self._tick, name="halo-fleet-hub-tick", daemon=True).start()
        if self.record:
            self._write_info()
        return self

    def _tick(self) -> None:
        while not self.stopping.wait(TICK_S):
            try:
                self.state.tick()
            except Exception:
                pass

    def url(self, host: Optional[str] = None) -> str:
        scheme = "https" if self.fingerprint else "http"
        host = host or (lan_address() if self.bind in ("0.0.0.0", "", "::") else self.bind)
        return f"{scheme}://{host}:{self.port}"

    def _write_info(self) -> None:
        from halo_harness.privateio import write_private_atomic
        info = {"pid": os.getpid(), "port": self.port, "bind": self.bind, "tls": bool(self.fingerprint),
                "fingerprint": self.fingerprint, "name": self.name, "url": self.url(),
                "admin_token": self.admin_token, "started": time.time()}
        write_private_atomic(hub_dir(self.home) / SERVE_FILE, json.dumps(info, indent=2))

    def stop(self) -> None:
        self.stopping.set()
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
        self.state.serving = {}
        if self.record:
            info = read_info(self.home, check_pid=False)
            if info and info.get("pid") == os.getpid() and info.get("port") == self.port:
                try:
                    (hub_dir(self.home) / SERVE_FILE).unlink()
                except OSError:
                    pass


def lan_address() -> str:
    """This machine's LAN address (the interface its default route uses; a
    UDP socket's `connect` sends nothing, and the probe is a documentation
    address, RFC 5737), else 127.0.0.1."""
    for probe in ("192.0.2.1", "198.51.100.1"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((probe, 9))
                addr = s.getsockname()[0]
            if addr and not addr.startswith("0."):
                return addr
        except OSError:
            continue
    return "127.0.0.1"


def read_info(home=None, *, check_pid: bool = True) -> Optional[dict]:
    path = hub_dir(home if home is not None else identity.home()) / SERVE_FILE
    try:
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict) or not isinstance(info.get("port"), int):
        return None
    if check_pid:
        from halo_harness.bg_run import pid_alive
        if info.get("pid") != os.getpid() and not pid_alive(info.get("pid")):
            return None
    return info


def running_call(home=None, method: str = "GET", route: str = "local/state", body: Optional[dict] = None,
                 timeout: float = 5.0) -> "Optional[tuple]":
    """`(status, body)` from the hub this machine runs in another process (admin token, loopback), or None."""
    info = read_info(home)
    if info is None:
        return None
    try:
        if info.get("tls"):
            conn = http.client.HTTPSConnection("127.0.0.1", info["port"], timeout=timeout, context=tls.client_context())
        else:
            conn = http.client.HTTPConnection("127.0.0.1", info["port"], timeout=timeout)
        conn.connect()
        if info.get("tls"):
            tls.check_pin(conn.sock, info.get("fingerprint"))
        conn.request(method, f"{protocol.PREFIX}/{route}", body=protocol.encode(body) if body is not None else None,
                     headers={protocol.H_ADMIN: str(info.get("admin_token")), "Content-Type": "application/json"})
        resp = conn.getresponse()
        status, data = resp.status, resp.read()
        conn.close()
        return status, json.loads(data.decode("utf-8") or "{}")
    except (OSError, ValueError, http.client.HTTPException):
        return None


def running_view(home=None, timeout: float = 3.0) -> Optional[dict]:
    """The merged view of the hub this machine runs in another process, or None."""
    got = running_call(home, timeout=timeout)
    return got[1] if got and got[0] == 200 and isinstance(got[1], dict) else None
