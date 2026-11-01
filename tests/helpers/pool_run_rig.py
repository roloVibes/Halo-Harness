"""tests.helpers.pool_run_rig -- Halo 3.3.8.0 R3: a pool that runs, with nothing real started.

`RunRig()` is tests/helpers/host_act_rig.PeerRig (this process's home is the controller; `pc-host`, a real
host/service.HostService on 127.0.0.1:0 in a second scratch home, serves `pc`, a MockUpstream Ollama on 127.0.0.1)
plus:
  - `FakeRpc` as host/rpc_runner.SEAMS: it records each rpc-server argv and, standing in for the process, listens on
    127.0.0.1:<-p> (nothing accepts) and writes rpc-server's "Starting RPC server v3.0.0" line to the log;
  - local_pool/versions.SEAMS["run"]: `--version` answers (llama-server and rpc-server both b7300 unless told);
  - the controller's llama-server = tests/helpers/fake_llama_server.py (huggingface.llama_server_bin), bound to
    127.0.0.1 (pool.bind), loading no model;
  - two members: `pc` (the paired host pc-host, its card: 24 GB with qwen3.8:27b resident) and `me` (this machine,
    `local`: a 40 GB card through studio/ollama_hosts_view.READERS), and the Qwen3-Next GGUF as a tiny file in a
    model folder (`gguf=False` leaves it out).
No model call, no real rpc-server or llama-server, never a request beyond 127.0.0.1 (the host rig refuses one).
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path

from tests.helpers.host_act_rig import PeerRig

FAKE = Path(__file__).resolve().parent / "fake_llama_server.py"
GIB, MIB = 2 ** 30, 2 ** 20
QWEN = "qwen3-next-80b-a3b-q4km"
CARD40 = {"gpus": [{"id": "0", "name": "a 40 GB card", "library": "CUDA", "total_bytes": 40 * 1024 * MIB}],
          "unified": False, "ram_bytes": 64 * GIB, "other_users": [], "loaded": [], "sources": [], "read_at": "fixture",
          "server": {"version": "0.40.6", "kv_cache_type": "f16"}}


class FakeRpc:
    def __init__(self) -> None:
        self.argvs, self.socks, self.n = [], {}, 0

    def start(self, argv: list, log: Path) -> int:
        self.argvs.append(list(argv))
        port = int(argv[argv.index("-p") + 1])
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", port))
        s.listen(16)
        self.n += 1
        pid = 4_200_000 + self.n
        self.socks[pid] = s
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"Starting RPC server v3.0.0\n  endpoint       : {argv[argv.index('-H') + 1]}:{port}\n")
        return pid

    def alive(self, pid) -> bool:
        return pid in self.socks

    def stop(self, pid) -> str:
        s = self.socks.pop(pid, None)
        if s is not None:
            s.close()
            return "terminated"
        return "already gone"

    def kill_all(self) -> None:
        for pid in list(self.socks):
            self.stop(pid)


class rpc_seams:
    """`with rpc_seams(build) as fake:` FakeRpc as host/rpc_runner.SEAMS, pool.rpc_server_bin set, and `--version`
    answering b<build> for rpc-server (local_pool/versions.SEAMS) -- for a host rig that is not a RunRig."""

    def __init__(self, build: int = 7300) -> None:
        self.build = build

    def __enter__(self) -> FakeRpc:
        from halo_harness.host import rpc_runner
        from halo_harness.local_pool import versions
        from halo_harness.theme import set_config_value
        self.fake = FakeRpc()
        rpc_runner.SEAMS.update(start=self.fake.start, alive=self.fake.alive, stop=self.fake.stop)
        versions.forget()
        versions.SEAMS["run"] = lambda argv: (0, f"version: {self.build} (fa1ec0de)")
        set_config_value("pool.rpc_server_bin", ["rpc-server"])
        return self.fake

    def __exit__(self, *exc) -> None:
        from halo_harness.host import rpc_runner
        from halo_harness.local_pool import versions
        self.fake.kill_all()
        rpc_runner.SEAMS.clear()
        versions.SEAMS.clear()
        versions.forget()


class RunRig(PeerRig):
    def __init__(self, *, rpc_build: int = 7300, llama_build: int = 7300, gguf: bool = True, cap: str = "all",
                 grants=("control",), card=None) -> None:
        super().__init__(cap=cap, grants=grants, card=card)
        self.rpc_build, self.llama_build, self.want_gguf = rpc_build, llama_build, gguf

    def _version(self, argv: list):
        text = " ".join(argv)
        if "fake_llama_server" in text:
            return 0, f"version: {self.llama_build} (fa1ec0de)\nbuilt with a fake compiler for the tests"
        if "rpc-server" in text:
            return 0, f"version: {self.rpc_build} (fa1ec0de)"
        return 127, "unknown binary"

    def __enter__(self) -> "RunRig":
        super().__enter__()
        from halo_harness.host import rpc_runner
        from halo_harness.local_pool import members as M, versions
        from halo_harness.local_sched import facts as F, lease
        from halo_harness.studio import ollama_hosts_view as V
        from tests.helpers.pool_rig import free_port
        self.fake = FakeRpc()
        self._dynamic_card()
        rpc_runner.SEAMS.update(start=self.fake.start, alive=self.fake.alive, stop=self.fake.stop)
        versions.forget()
        versions.SEAMS["run"] = self._version
        lease.reset()
        V.READERS["card"] = lambda h: dict(CARD40) if h.name == "me" else None
        F.SEAMS["loaded"] = lambda h: []
        V.reset_cache()
        self.models = Path(self.rig.root_p) / "models"
        if self.want_gguf:
            snap = self.models / "models--Qwen--Qwen3-Next-80B-A3B-Instruct-GGUF" / "snapshots" / "c0de"
            snap.mkdir(parents=True)
            (snap / "Qwen3-Next-80B-A3B-Instruct-Q4_K_M.gguf").write_bytes(b"GGUF" + b"\0" * 60)
        self.models.mkdir(parents=True, exist_ok=True)
        self.rig.set_peer(**{"ollama.hosts": [{"name": "pc", "url": self.peer_url},
                                              {"name": "me", "url": "http://127.0.0.1:9", "default": True}],
                             "huggingface.llama_server_bin": [sys.executable, str(FAKE)],
                             "pool.rpc_server_bin": ["rpc-server"], "pool.bind": "127.0.0.1",
                             "huggingface.model_dirs": [str(self.models)]})
        self.rpc_port = free_port()
        M.add("pc", f"pc-host:{self.rpc_port}", state_dir=self.peer)
        M.add("me", "local", state_dir=self.peer)
        return self

    def _dynamic_card(self) -> None:
        """The host's card drops a model the moment the host unloads it (and takes it back when it loads it), the
        way a fresh read of /api/ps would: the unload and the load go to the mock Ollama, recorded here."""
        from halo_harness.providers import ollama_load as L
        from tests.helpers.ollama_panel_seed import cards
        base, self.gone, self._ol = (self.card_ or cards()["pc"]), set(), (L.unload, L.load)

        def unload(host, model):
            got = self._ol[0](host, model)
            if got.get("ok"):
                self.gone.add(model)
            return got

        def load(host, model, **kw):
            got = self._ol[1](host, model, **kw)
            if got.get("ok"):
                self.gone.discard(model)
            return got
        L.unload, L.load = unload, load
        self.svc.view.readers["card"] = lambda h: {**base, "loaded": [m for m in base.get("loaded") or []
                                                                    if m.get("model") not in self.gone]}

    def __exit__(self, *exc) -> None:
        from halo_harness.providers import ollama_load as L
        L.unload, L.load = self._ol
        from halo_harness.host import rpc_runner
        from halo_harness.local_pool import launch, peer, versions
        from halo_harness.local_sched import facts as F, lease
        from halo_harness.studio import ollama_hosts_view as V
        try:
            r = launch.run(self.peer)
            if r and launch.alive(r):
                from halo_harness.local_pool.spawn import halt
                halt(r["pid"])
        finally:
            self.fake.kill_all()
            rpc_runner.SEAMS.clear()
            versions.SEAMS.clear()
            versions.forget()
            lease.reset()
            peer.reset()
            V.READERS.pop("card", None)
            F.SEAMS.pop("loaded", None)
            V.reset_cache()
            super().__exit__(*exc)
