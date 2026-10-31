"""halo_harness.host.service -- `halo host serve`: the host process (Halo 3.3.7.0 R1; docs/HOST.md).

`HostService(home, port=7431, bind="0.0.0.0")` is one process with no TUI, no session and no model. `start()`:

- does not start under offline mode (`network.offline`, `--offline`) with fleet/hub.py's `FleetOffline` line;
- serves the signed `/host/v1/` routes (host/http.py) on its LAN port, inside TLS with its own self-signed
  certificate (fleet/tls.py, under `<state>/host/`) when `cryptography` is there, HMAC-signed HTTP otherwise;
- starts the steward's watch for the hosts this machine serves (`ollama_steward/job.start_for(home, where="host")`:
  the log tail, the `/api/ps` poll, the events and fingerprints, `probe_new`, the remote tails; in `where="host"` the
  steward's rules only report: no change is applied and no model writes a note) -- one job per state dir, so a
  Studio or a hub already running it keeps it; and the resources sampler;
- drives the ledger forwarder (fleet/ollama_share.Forwarder) to every hub this machine joined with its own loop,
  so the hub sees this machine's calls with no session open, and announces itself to that hub (`POST
  /fleet/v1/host {host: true, port, fingerprint, url, serves}`, fleet/hub_hosts.py) every ANNOUNCE_S;
- writes `<state>/host/serve.json` (host/state.py); `halo host stop` writes the stop file and the loop ends.
"""

from __future__ import annotations

import http.server
import os
import secrets
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from halo_harness.fleet import identity, protocol, tls
from halo_harness.fleet.hub import FleetOffline, lan_address
from halo_harness.fleet.hub_join import JoinGate
from halo_harness.host import state as S
from halo_harness.host.http import Handler
from halo_harness.host.routes_view import View

TICK_S = 0.5
FORWARD_S = 2.0
ANNOUNCE_S = 60.0
OFFLINE_LINE = ("offline mode is on (--offline or network.offline): the host listens on the LAN, so it does not "
                "start; `/offline off` or drop --offline first")


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, addr, svc, ssl_ctx) -> None:
        self.svc, self.ssl_ctx = svc, ssl_ctx
        super().__init__(addr, Handler)

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def handle_error(self, request, client_address):  # a peer that hung up between two requests is not an error
        import sys
        if not isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            super().handle_error(request, client_address)

    def finish_request(self, request, client_address):
        if self.ssl_ctx is not None:
            request.settimeout(10)
            try:
                request = self.ssl_ctx.wrap_socket(request, server_side=True)
            except OSError:
                return
        super().finish_request(request, client_address)


def _default_job(home):
    from halo_harness.ollama_steward.job import start_for
    return start_for(home, where="host")


class HostService:
    def __init__(self, home=None, *, port: Optional[int] = None, bind: Optional[str] = None,
                 name: Optional[str] = None, tls_on: Optional[bool] = None, readers: Optional[dict] = None,
                 job: Optional[Callable] = None, forward: bool = True, record: bool = True,
                 advertise: Optional[str] = None) -> None:
        self.home = Path(home) if home is not None else identity.home()
        self.port = S.port(self.home) if port is None else int(port)
        self.bind = bind or S.bind(self.home)
        self.name = (name or identity.fleet_name(self.home)).strip()[:64]
        self.identity = identity.harness(self.home)
        self.tls_on, self.record, self.forward, self.advertise = tls_on, record, forward, advertise
        self.pairing = S.HostPairing(self.home)
        self.guard, self.gate = protocol.ReplayGuard(), JoinGate()
        self.view = View(self.home, readers)
        self.stopping = threading.Event()
        self.server: Optional[_Server] = None
        self.fingerprint: Optional[str] = None
        self.started: Optional[float] = None
        self.job_factory = job or _default_job
        self.job = None
        self.link_id = secrets.token_hex(8)
        self._links: dict = {}
        self.forward_state: dict = {}  # hub url -> {at, sent, error, announced}

    # ---- fleet/hub_join.handle_join reads these ---------------------------------------------------
    def reload(self, force: bool = False, quiet: bool = False) -> None:
        return None

    def hub_public(self) -> dict:
        from halo_harness import __version__
        return {"id": self.identity.get("id"), "name": self.name, "version": __version__, "tls": bool(self.fingerprint),
                "fingerprint": self.fingerprint, "host": True}

    def public(self) -> dict:
        return {**self.hub_public(), "port": self.port, "started": self.started, "url": self.url()}

    def addr(self) -> str:
        if self.advertise:  # the address peers reach it at, when the bind does not say it (the tests' placeholder)
            return self.advertise
        return lan_address() if self.bind in ("0.0.0.0", "", "::") else self.bind

    def url(self) -> str:
        return f"{'https' if self.fingerprint else 'http'}://{self.addr()}:{self.port}"

    # ---- start / stop -----------------------------------------------------------------------------
    def start(self) -> "HostService":
        if identity.offline():
            raise FleetOffline(OFFLINE_LINE)
        ctx = None
        if self.tls_on is not False:
            got = tls.ensure_cert(S.host_dir(self.home), self.name or "halo-host")
            if got is None and self.tls_on:
                raise RuntimeError("TLS needs the `cryptography` package (pip install 'halo-harness[fleet]')")
            if got is not None:
                ctx, self.fingerprint = tls.server_context(got[0], got[1]), got[2]
        S.clear_stop(self.home)
        self.server = _Server((self.bind, self.port), self, ctx)
        self.port = self.server.server_address[1]
        self.started = time.time()
        threading.Thread(target=self.server.serve_forever, name="halo-host-http", daemon=True).start()
        try:
            self.job = self.job_factory(self.home)
        except Exception:
            self.job = None
        try:
            from halo_harness.config.paths import background_net_disabled
            from halo_harness.ollama_steward import resources
            resources.want(self.home, "host", True, lease=None, start=not background_net_disabled())
        except Exception:
            pass
        if self.record:
            self._write_info()
        threading.Thread(target=self._loop, name="halo-host-loop", daemon=True).start()
        return self

    def watches(self) -> list:
        return [h.name for h in self.view.hosts()]

    def _write_info(self) -> None:
        S.write_info(self.home, {"pid": os.getpid(), "port": self.port, "bind": self.bind, "tls": bool(self.fingerprint),
                                 "fingerprint": self.fingerprint, "name": self.name, "url": self.url(),
                                 "started": self.started, "grants_file": str(S.host_dir(self.home) / S.PEERS_FILE),
                                 "watches": self.watches(), "steward_job": self.job is not None})

    def _loop(self) -> None:
        nxt = 0.0
        while not self.stopping.wait(TICK_S):
            if S.stop_path(self.home).exists():
                self.stopping.set()
                break
            if time.monotonic() >= nxt:
                nxt = time.monotonic() + FORWARD_S
                try:
                    if self.forward:
                        self.forward_tick()
                    from halo_harness.host.verify import tick  # 3.3.7.0 R2: the fix loop's verify windows
                    tick(self)
                except Exception:
                    pass
        self._shutdown()

    def stop(self) -> None:
        self.stopping.set()
        self._shutdown()

    def _shutdown(self) -> None:
        if getattr(self, "_down", False):
            return
        self._down = True
        if self.job is not None:
            try:
                self.job.stop()
            except Exception:
                pass
            self.job = None
        try:
            from halo_harness.ollama_steward import resources
            resources.want(self.home, "host", False)
        except Exception:
            pass
        for link in list(self._links.values()):
            link["link"].close()
        self._links.clear()
        if self.server is not None:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
        if self.record:
            S.drop_info(self.home, os.getpid(), self.port)
        S.clear_stop(self.home)

    # ---- the hubs this machine joined: its ledger lines and its announce ---------------------------
    def forward_tick(self, now: Optional[float] = None) -> int:
        """One pass over the joined hubs; returns how many ledger lines went. Never raises."""
        from halo_harness.fleet import ollama_share, store
        from halo_harness.fleet.relay import HubError, HubLink
        if identity.offline():
            return 0
        now = time.monotonic() if now is None else now
        sent = 0
        for entry in store.hubs(self.home):
            if entry.get("state", "joined") != "joined":
                continue
            ref = str(entry.get("hub_id") or entry.get("url"))
            got = self._links.get(ref)
            if got is None:
                key = store.key_for(entry, self.home)
                if key is None:
                    continue
                got = self._links[ref] = {"link": HubLink(entry, key, self.identity["id"], timeout=5.0),
                                          "fwd": ollama_share.Forwarder(entry, home=self.home), "announced": -ANNOUNCE_S}
                got["fwd"].last_flush = 0.0  # the first pass sends what waits
            st = self.forward_state.setdefault(entry["url"], {"sent": 0, "error": "", "announced": None})
            try:
                if now - got["announced"] >= ANNOUNCE_S or got["announced"] < 0:
                    got["link"].request("POST", protocol.PREFIX + "/host", protocol.doc(
                        link=self.link_id, host=True, port=self.port, fingerprint=self.fingerprint, url=self.url(),
                        name=self.name, serves=S.served_rows(self.addr(), self.view.hosts())))
                    got["announced"], st["announced"] = now, time.time()
                n = got["fwd"].tick(got["link"], self.link_id)
                st.update(sent=st["sent"] + n, error="", at=time.time())
                sent += n
            except HubError as e:
                st["error"] = str(e)[:200]
                got["announced"] = now - ANNOUNCE_S + 30.0  # tried again in half a minute
        return sent
