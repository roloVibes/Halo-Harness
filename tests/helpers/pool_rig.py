"""tests.helpers.pool_rig -- Halo 3.3.8.0 R1: a scratch home for the pool's tests (local_pool/, pool_cli.py,
studio/pool_api.py). `PoolHome()` scopes this process to a fresh BRIDGE_TEST_HOME with the test flag on and OLLAMA_HOST
at 127.0.0.1:9; `rows(*free)` builds budget rows by hand for the fit's arithmetic (worker1.local, worker2.local, ...);
`rpc_listener()` is a plain TCP listener on 127.0.0.1:0 standing in for an rpc-server (it listens, nothing more). No model call, no real network: every address a fixture names is 127.0.0.1, a 192.0.2.x placeholder or a
worker1.local-style name, and the probe asks only 127.0.0.1 under the test flag. Every variable it touches is restored.
"""
from __future__ import annotations

import os
import shutil
import socket
import tempfile

_VARS = ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR", "BRIDGE_TEST_NO_BACKGROUND_NET", "OLLAMA_HOST", "HALO_OFFLINE")


def rows(*free, link="1 GbE", stated=False) -> list:
    return [{"name": f"worker{i + 1}", "host": f"worker{i + 1}.local", "rpc_port": 50052, "free_gb": f,
             "total_gb": f, "vram_source": "stated" if stated else "card", "link_word": link, "rtt_word": "0.4 ms"}
            for i, f in enumerate(free)]


class PoolHome:
    def __init__(self, config: "dict | None" = None) -> None:
        self._saved = {k: os.environ.get(k) for k in _VARS}
        for k in ("BRIDGE_STATE_DIR", "HALO_OFFLINE"):
            os.environ.pop(k, None)
        self.root = tempfile.mkdtemp(prefix="hp_pool-")
        os.environ.update(BRIDGE_TEST_HOME=self.root, BRIDGE_TEST_NO_BACKGROUND_NET="1", OLLAMA_HOST="http://127.0.0.1:9")
        from halo_harness.config.paths import bridge_home
        self.state = bridge_home()
        for k, v in (config or {}).items():
            self.config(**{k: v})

    def config(self, **values) -> None:
        from halo_harness.theme import set_config_value
        for k, v in values.items():
            set_config_value(k, v)

    def __enter__(self) -> "PoolHome":
        return self

    def __exit__(self, *exc) -> None:
        from halo_harness.local_pool import link
        from halo_harness.providers import rpc_probe
        link.RUNNER.clear()
        rpc_probe.SEAMS.clear()
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.root, ignore_errors=True)


class rpc_listener:
    """`with rpc_listener() as port:` a TCP listener on 127.0.0.1:0 standing in for an rpc-server. It never accepts:
    the kernel completes each connect from the listen backlog, so no thread of this process wakes for it and the
    probe's measured connect is the stack's own (an accepting thread here would add GIL hand-offs of ~5 ms each)."""

    def __enter__(self) -> int:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(256)
        return self.sock.getsockname()[1]

    def __exit__(self, *exc) -> None:
        self.sock.close()


def free_port() -> int:
    """A port nothing listens on (bound, then closed)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port
