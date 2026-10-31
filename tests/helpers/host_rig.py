"""tests.helpers.host_rig -- Halo 3.3.7.0 R1: a fake `halo host` beside this process's home.

`HostRig()` scopes this process to a scratch home (the peer, `bob@peer`, whose `ollama.hosts` has `pc` at
http://192.0.2.10:11434: a placeholder no request ever reaches) and, in a second scratch home H (`pc-host`), runs a
real host/service.HostService on 127.0.0.1:0 whose host/routes_view.View reads fixture data instead of a server
(`readers`: the Ollama panel seed's card and catalog for `pc`, a fixture tail with a request-body line, a fixture log
status), advertising 192.0.2.10 so the peer's `pc` entry matches it. H holds a fixture ledger (a peer's lines), two
server events and a battery profile for qwen3.8:27b. `pair()` runs the real six-word exchange (host/join.py) and
keeps the entry in the peer's fleet.json. `host_home=None` runs the host on this process's own home instead (the CLI
tests). No model call, no real ssh, never a request beyond 127.0.0.1. Every variable it touches is restored.
"""
from __future__ import annotations

import json
import sys
import os
import shutil
import tempfile
import time
from pathlib import Path

PC = {"name": "pc", "url": "http://192.0.2.10:11434"}
ADDR = "192.0.2.10"
BIG, CODER = "qwen3.8:27b", "qwen3-coder:30b"
BODY = 'time=2026-10-31T08:00:02.000Z level=DEBUG source=routes.go:1 msg="chat request" prompt="the secret plan"'
TAIL = ['time=2026-10-31T08:00:00.000Z level=INFO source=server.go:1 msg="load" offloaded 59/66 layers to GPU',
        'time=2026-10-31T08:00:01.000Z level=WARN source=runner.go:1 msg="truncating input prompt" limit=16386 '
        'prompt=41104 keep=4 new=16386', BODY]
LOG = {"state": "live", "line": "live, last line 4 s ago", "path": "%LOCALAPPDATA%/Ollama/server.log",
       "readable": True, "last_line_at": None, "debug": True, "why": "", "rung": "local", "tail_cli": ""}
_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST", "HALO_OFFLINE",
         "HALO_FLEET_PRIVATE")


def pc_host():
    from halo_harness.providers.ollama import OllamaHost
    return OllamaHost(name="pc", url=PC["url"])


def readers() -> dict:
    from tests.helpers.ollama_panel_seed import cards, catalogs
    return {"hosts": lambda: [pc_host()], "card": lambda h: cards()["pc"], "catalog": lambda h: catalogs()["pc"],
            "tail": lambda h, n: (TAIL[-n:], "%LOCALAPPDATA%/Ollama/server.log", None),
            "log": lambda h: dict(LOG)}


def profile(model: str = BIG, host: str = "pc") -> dict:
    return {"model": model, "host": host, "digest": "sha256:0b27", "ollama_version": "0.40.6", "probe_set": "battery-3",
            "probed_at": time.time() - 3600, "tools": "yes", "vision": "no", "sits": "a capable sub-agent",
            "agentic_ready": True, "evidence": {"tools": "the call came back"}}


def seed_host(home: Path) -> None:
    from halo_harness.ollama_steward.ledger import append_lines
    from halo_harness.ollama_steward.server_events import record_events
    from halo_harness.providers.ollama_capability import save_profile
    from tests.helpers.steward_seed import event, line
    append_lines(home, [line(model=BIG, ago=300 + i) for i in range(3)] + [{**line(model=CODER, ago=200), "from": "mac@lab"}])
    record_events(home, [event("prompt-trimmed", model=BIG, ago=900, limit=16386, prompt=41104),
                         event("load-result", model=BIG, ago=600, layers=[66, 66], splits=2)], host="pc")
    save_profile(home, profile())


class HostRig:
    def __init__(self, *, host_home: "Path | None | bool" = False, readers_=None, job=None, forward=False,
                 tls_on=None, seed: bool = True) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in ("BRIDGE_STATE_DIR", "HALO_OFFLINE", "HALO_FLEET_PRIVATE"):
            os.environ.pop(k, None)
        self.root_p = tempfile.mkdtemp(prefix="hs_peer-")
        os.environ.update(BRIDGE_TEST_HOME=self.root_p, BRIDGE_TEST_NO_BACKGROUND_NET="1", OLLAMA_HOST="http://127.0.0.1:9")
        self.set_peer(**{"fleet.name": "bob@peer", "ollama.hosts": [PC]})
        from halo_harness.config.paths import bridge_home
        self.peer = bridge_home()
        if host_home is None:
            self.root_h, self.home = None, self.peer
        else:
            self.root_h = tempfile.mkdtemp(prefix="hs_host-")
            self.home = Path(self.root_h) / ".halo"
            self.home.mkdir(parents=True)
            (self.home / "config.json").write_text(json.dumps({"fleet": {"name": "pc-host"}}), encoding="utf-8")
        if seed:
            seed_host(self.home)
        self.readers = readers() if readers_ is None else readers_
        self.job, self.forward, self.tls_on = job, forward, tls_on
        self.svc = None
        self._reset()
        self._direct()
        self.blocked: list = []
        import socket
        self._create = socket.create_connection

        def guard(address, *a, **kw):  # nothing in a host test leaves 127.0.0.1: an attempt is recorded and refused
            if str(address[0]) not in ("127.0.0.1", "localhost", "::1"):
                import traceback
                self.blocked.append(address)
                sys.stderr.write(f"host rig: refused {address}\n" + "".join(traceback.format_stack(limit=12)))
                raise OSError(f"the host rig keeps every request on 127.0.0.1 (asked {address[0]})")
            return self._create(address, *a, **kw)
        socket.create_connection = guard

    @staticmethod
    def _direct(on: bool = True) -> None:
        """The peer's direct-API rung for pc (`/api/tags` + `/api/show`) reads the fixture: no request to 192.0.2.10."""
        from halo_harness.providers import ollama as O
        from halo_harness.studio import ollama_hosts_view as V
        from tests.helpers.ollama_panel_seed import catalogs
        if on:
            V.READERS["catalog"] = lambda h: catalogs().get(h.name, {"models": []})
            with O._CATALOG_LOCK:
                O._CATALOG_CACHE[PC["url"]] = (time.monotonic() + 3600, catalogs()["pc"])
        else:
            V.READERS.pop("catalog", None)
            O.reset_catalog_cache()

    @staticmethod
    def _reset() -> None:
        from halo_harness.fleet import identity
        from halo_harness.ollama_steward import host_client
        from halo_harness.studio import ollama_hosts_view as V
        identity.forget_cache()
        host_client.reset()
        V.reset_cache()

    def set_peer(self, **values) -> None:
        from halo_harness.fleet import identity
        from halo_harness.theme import set_config_value
        for k, v in values.items():
            set_config_value(k, v)
        identity.forget_cache()

    def start(self) -> "HostRig":
        from halo_harness.host.service import HostService
        self.svc = HostService(self.home, port=0, bind="127.0.0.1", advertise=ADDR, readers=self.readers,
                               job=self.job or (lambda h: None), forward=self.forward, tls_on=self.tls_on).start()
        return self

    def url(self) -> str:
        return f"{'https' if self.svc.fingerprint else 'http'}://127.0.0.1:{self.svc.port}"

    def pair(self, harness: "dict | None" = None) -> dict:
        """The six-word exchange; the entry lands in this process's fleet.json. With the host on this process's own
        home, a peer harness of another (scratch) home pairs instead (`self.peer_id` signs its requests)."""
        from halo_harness.fleet import identity, store
        from halo_harness.host.join import join
        if harness is None and self.root_h is None:
            self._other = tempfile.mkdtemp(prefix="hs_other-")
            harness = {**identity.harness(Path(self._other)), "name": "carol@peer"}
        me = harness or identity.harness()
        self.peer_id = me["id"]
        got = join(f"127.0.0.1:{self.svc.port}", self.svc.pairing.new_code(600)[0], me)
        key = got.pop("key")
        entry = store.add_host(got, key)
        self.key = key
        self._reset()
        return entry

    def client(self):
        from halo_harness.fleet import store
        from halo_harness.ollama_steward.host_client import HostClient, for_host
        if self.root_h is None:  # the peer is another home's harness: sign as it
            return HostClient(store.hosts()[-1], self.key, self.peer_id)
        return for_host(pc_host())

    def __enter__(self) -> "HostRig":
        return self

    def __exit__(self, *exc) -> None:
        if self.svc is not None:
            self.svc.stop()
        self._direct(False)
        self._reset()
        import socket
        socket.create_connection = self._create
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        from halo_harness.fleet import identity
        identity.forget_cache()
        for root in (self.root_p, self.root_h, getattr(self, "_other", None)):
            if root:
                shutil.rmtree(root, ignore_errors=True)
        if self.blocked and exc[0] is None:
            raise AssertionError(f"a request tried to leave 127.0.0.1: {self.blocked[:3]}")
