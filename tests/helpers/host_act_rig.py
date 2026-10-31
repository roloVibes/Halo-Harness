"""tests.helpers.host_act_rig -- Halo 3.3.7.0 R2: a fake `halo host` that acts, over a fake Ollama on 127.0.0.1:0.

`ActRig(cap="all", grants=("control",))` runs tests/helpers/host_rig.HostRig with the host on this process's own
scratch home (so the profile fields a fix lands go to the host's config.json, as on a real host) and a second scratch
harness, `carol@peer`, as the peer that signs every request. The host serves one Ollama host, `pc`, which is a
MockUpstream on 127.0.0.1 (the models qwen3.8:27b, qwen3-coder:30b, qwen3.5:9b: `/api/tags`, `/api/show`,
`/api/ps`, the load / unload generate, the pull); its hardware card is the Ollama panel seed's 24 GB card with
ComfyUI holding 2 GB. `fleet.allow_control` is `cap`; the peer holds `grants`.

    rig.act(grant, op, params, **kw) -> (status, answer)     one signed request, its HTTP status kept
    rig.lines(model, n, tok_s=, trimmed=, ago=)             ledger lines on the host for pc (the verify's calls)
    rig.mock, rig.svc, rig.home, rig.client(), rig.host

No model is called, nothing leaves 127.0.0.1, no real Ollama is touched.
"""

from __future__ import annotations

import time

from tests.helpers.host_rig import BIG, CODER, HostRig
from tests.helpers.mock_ollama import MockUpstream

SMALL = "qwen3.5:9b"
GIB = 2 ** 30


def _rows() -> dict:
    from tests.helpers.steward_seed import rows
    return rows()


def mock_for() -> MockUpstream:
    r = _rows()
    tags = {"models": [{"name": m, "model": m, "size": r[m]["size"], "digest": f"sha256:{i}0b27", "details":
                        r[m]["details"]} for i, m in enumerate((BIG, CODER, SMALL))]}
    show = {m: {"capabilities": r[m]["capabilities"], "details": r[m]["details"], "model_info": r[m]["model_info"],
                "parameters": "", "template": "", "modelfile": ""} for m in (BIG, CODER, SMALL)}
    return MockUpstream(tags_response=tags, show_responses=show).start()


class ActRig:
    def __init__(self, *, cap: str = "all", grants=("control",), card=None) -> None:
        self.cap, self.grants_, self.card_ = cap, tuple(grants), card

    def __enter__(self) -> "ActRig":
        from halo_harness.providers.ollama import OllamaHost
        from tests.helpers.ollama_panel_seed import cards
        self.mock = mock_for()
        self.host = OllamaHost(name="pc", url=self.mock.base_url)
        card = self.card_ or cards()["pc"]
        r = _rows()
        readers = {"hosts": lambda: [self.host], "card": lambda h: card,
                   "catalog": lambda h: {"models": [r[BIG], r[CODER], r[SMALL]]},
                   "tail": lambda h, n: ([], "fixture", None), "log": lambda h: {"state": "live", "line": "live"}}
        self.rig = HostRig(host_home=None, readers_=readers, seed=False).__enter__()
        self.rig.set_peer(**{"fleet.allow_control": self.cap, "ollama.steward.probe_new": False})
        self.svc = self.rig.start().svc
        self.home = self.svc.home
        self.entry = self.rig.pair()
        from halo_harness.host import grants
        for g in self.grants_:
            grants.grant(self.home, self.rig.peer_id, g)
        return self

    def __exit__(self, *exc) -> None:
        try:
            self.rig.__exit__(*exc)
        finally:
            self.mock.stop()

    def client(self):
        return self.rig.client()

    def act(self, grant: str, op: str, params: dict, **kw) -> "tuple[int, dict]":
        from halo_harness.ollama_steward.host_client import HostError
        try:
            got = self.client().act(grant, op, params, **kw)
        except HostError as e:
            return e.status, {"error": str(e)}
        return (202 if got.get("queued") else 200), got

    def get(self, route: str) -> "tuple[int, dict]":
        from halo_harness.ollama_steward.host_client import HostError
        try:
            return 200, self.client().get(route)
        except HostError as e:
            return e.status, {"error": str(e)}

    def lines(self, model: str, n: int, *, tok_s: float = 40.0, trimmed: bool = False, ago: float = 0.0,
              cut: bool = False) -> None:
        from halo_harness.ollama_steward.ledger import append_lines
        from tests.helpers.steward_seed import line
        rows = [line(host={"name": "pc", "url": self.mock.base_url}, model=model, eval_tok_s=tok_s, trimmed=trimmed,
                     ago=ago - i * 0.01, **({"done_reason": "length"} if cut else {})) for i in range(n)]
        append_lines(self.home, rows)

    def wait_job(self, jid: str, timeout: float = 15.0) -> dict:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            status, got = self.get(f"job/{jid}")
            job = got.get("job") or {}
            if job.get("done"):
                return job
            time.sleep(0.1)
        return self.get(f"job/{jid}")[1].get("job") or {}


class PeerRig(ActRig):
    """The peer side: this process's home is the peer (`bob@peer`, whose `ollama.hosts` has pc at the placeholder
    192.0.2.10 with the fake's port, so it matches what the host serves), the host runs on a second scratch home. The
    host's profile writes land in this process's config.json too (one process): the tests read the host's own
    change rows and fix rows, which are under its home."""

    def __enter__(self) -> "PeerRig":
        from halo_harness.providers.ollama import OllamaHost
        from tests.helpers.ollama_panel_seed import cards
        self.mock = mock_for()
        self.host = OllamaHost(name="pc", url=self.mock.base_url)
        card = self.card_ or cards()["pc"]
        r = _rows()
        readers = {"hosts": lambda: [self.host], "card": lambda h: card,
                   "catalog": lambda h: {"models": [r[BIG], r[CODER], r[SMALL]]},
                   "tail": lambda h, n: ([], "fixture", None), "log": lambda h: {"state": "live", "line": "live"}}
        self.rig = HostRig(readers_=readers, seed=False).__enter__()
        self.peer_url = f"http://192.0.2.10:{self.mock.port}"
        self.rig.set_peer(**{"ollama.hosts": [{"name": "pc", "url": self.peer_url}]})
        import json
        cfg = self.rig.home / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data.setdefault("fleet", {})["allow_control"] = self.cap
        data.setdefault("ollama", {}).setdefault("steward", {})["probe_new"] = False
        cfg.write_text(json.dumps(data), encoding="utf-8")
        self.svc = self.rig.start().svc
        self.home, self.peer = self.svc.home, self.rig.peer
        self.entry = self.rig.pair()
        from halo_harness.fleet import identity
        from halo_harness.host import grants
        for g in self.grants_:
            grants.grant(self.home, identity.harness()["id"], g)
        from halo_harness.ollama_steward import host_client
        host_client.reset()
        return self

    def client(self):
        from halo_harness.ollama_steward.host_client import for_host
        from halo_harness.providers.ollama import OllamaHost
        return for_host(OllamaHost(name="pc", url=self.peer_url))

    def studio(self, method: str, path: str, body=None, query=None) -> "tuple[int, dict]":
        from pathlib import Path
        from halo_harness.studio.api import Request, dispatch
        return dispatch(Request(method=method, path=path, query=query or {}, body=body or {}, cwd=Path(self.rig.root_p),
                                state_dir=self.peer, server=None))

    def peer_lines(self, model: str, n: int, *, tok_s: float = 40.0, ago: float = 0.0) -> None:
        from halo_harness.ollama_steward.ledger import append_lines
        from tests.helpers.steward_seed import line
        append_lines(self.peer, [line(host={"name": "pc", "url": self.peer_url}, model=model, eval_tok_s=tok_s,
                                      ago=ago - i * 0.01) for i in range(n)])
