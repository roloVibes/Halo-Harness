"""tests.test_host_tensorfold -- Halo 3.3.9.3 deliverable 5: a TensorFold server on the host machine through the host --
the Mac's case: it serves a model on TensorFold's Metal build and runs `halo host`, the PC and Kali reach it
(host/state.server_rows, host/routes_view.catalog's `tensorfold`, tensorfold/peer.py, tensorfold/route.py in
local_sched/place.py and place_advice.py). Over tests/helpers/host_act_rig.PeerRig: the host is a real
host/service.HostService on 127.0.0.1:0 whose machine runs a TensorFold server (a Server row, no process); its config
holds the `tensorfold` entry Halo writes for `--lan`; every address a 192.0.2.x placeholder or 127.0.0.1:

1. the join's `servers`: `kind: server`, `runtime: tensorfold`, its model -- what the peer matches by;
2. the host's catalog offers the entry and its key; a peer with no entry of that name resolves `hf:local/<model>@<the
   host's name>` to the TensorFold server, with the key; a loopback-only server is not offered;
3. placement: the peer's candidates include the host's TensorFold server; the model it serves is warm (no load), another
   model TensorFold's table names is a restart with the loading tax said (the checkpoint read into memory, the `tensorfold
   pull` if it is not there), a model TensorFold does not name is out.
No TensorFold runs, nothing is sent but to the host fake.
Run: python -m tests.test_host_tensorfold
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import PeerRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
MODEL = "Qwen3.8-27B-MLX-4bit"
KEY_ENV = "HALO_SECRET_TENSORFOLD_API_KEY"


class Rig:
    def __init__(self, lan: bool = True) -> None:
        self.lan = lan

    def __enter__(self):
        from halo_harness.ollama_steward.servers_hf import Server
        from halo_harness.tensorfold import peer
        self._key = os.environ.get(KEY_ENV)
        os.environ[KEY_ENV] = "fixture-tensorfold-key"
        self.srv = Server(name="tensorfold", url="http://127.0.0.1:18081", runtime="tensorfold", model=MODEL)
        self.peer = PeerRig(servers=[self.srv]).__enter__()
        cfg = Path(self.peer.home) / "config.json"
        data = json.loads(cfg.read_text(encoding="utf-8"))
        data.setdefault("huggingface", {})["local_servers"] = [
            {"name": "tensorfold", "url": "http://127.0.0.1:18081/v1", "runtime": "tensorfold", "model": MODEL,
             "tensorfold": True, "lan": self.lan, "api_key_env": KEY_ENV}]
        cfg.write_text(json.dumps(data), encoding="utf-8")
        peer.reset()
        return self

    def __exit__(self, *exc):
        from halo_harness.tensorfold import peer
        peer.reset()
        try:
            self.peer.__exit__(*exc)
        finally:
            if self._key is None:
                os.environ.pop(KEY_ENV, None)
            else:
                os.environ[KEY_ENV] = self._key


def _client():
    """The peer's signed client of the paired host (as tensorfold/peer.py asks it)."""
    from halo_harness.fleet import identity, store
    from halo_harness.ollama_steward.host_client import HostClient
    e = store.hosts()[-1]
    return HostClient(e, store.key_for(e), identity.harness()["id"])


@test
def test_the_join_lists_the_tensorfold_server(ctx: Ctx):
    from halo_harness.host import state as S
    with Rig() as r:
        rows = r.peer.entry.get("servers") or []
        tf = next((x for x in rows if x.get("runtime") == "tensorfold"), {})
        ctx.check(f"kind server, runtime tensorfold, its model, got {rows}", tf.get("kind") == "server"
                  and tf.get("name") == "tensorfold" and tf.get("model") == MODEL and tf.get("port") == 18081)
        ctx.check("served_rows carries the same row", any(x.get("runtime") == "tensorfold" and x.get("model") == MODEL
                                                          for x in S.served_rows("192.0.2.20", [], [r.srv])))


@test
def test_a_peer_reaches_it_by_the_hosts_name(ctx: Ctx):
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    with Rig() as r:
        got = _client().catalog(4096).get("tensorfold")
        ctx.check(f"the host's catalog offers it with its key, got {got}", got and got["url"] ==
                  "http://127.0.0.1:18081/v1" and got["api_key"] == "fixture-tensorfold-key" and got["model"] == MODEL)
        name = r.peer.entry["name"]
        s = resolve_huggingface_local_server(name)
        ctx.check(f"hf:local/{MODEL}@{name} resolves through the host, got {s}", s is not None and s.runtime ==
                  "tensorfold" and s.url == "http://127.0.0.1:18081/v1" and s.api_key == "fixture-tensorfold-key")
        ctx.check("a name no entry and no host has stays unresolved", resolve_huggingface_local_server("nobody") is None)
    with Rig(lan=False) as r:
        ctx.check("a loopback-only server is not offered", _client().catalog(4096).get("tensorfold") is None)


@test
def test_placement_sees_it_with_its_loading_tax(ctx: Ctx):
    from halo_harness.local_sched import place
    from halo_harness.local_sched.place_advice import candidates, tax
    from halo_harness.tensorfold.route import TfHost, tf_hosts
    with Rig() as r:
        name = r.peer.entry["name"]
        hosts = tf_hosts()
        h = next((x for x in hosts if x.name == name), None)
        ctx.check(f"the host's TensorFold server is a candidate, got {hosts}", h is not None and h.model == MODEL
                  and not h.local and h.url.endswith(":18081/v1") and any(isinstance(x, TfHost) for x in candidates()))
        warm = place.answer(h, {"lane": "worker", "model": f"hf:local/{MODEL}@{name}"})
        ctx.check(f"the model it serves: warm, no load, got {warm}", warm["warm"] and warm["fits"] is True
                  and warm["via"] == "tensorfold" and tax(warm) == "warm: no load")
        other = place.answer(h, {"lane": "worker", "model": "nvidia/Qwen3.6-35B-A3B-NVFP4"})
        ctx.check(f"another model: the restart and its tax, got {tax(other)!r}", other["fits"] is None
                  and other["load_s"] == 15.0 and tax(other) == "a restart onto Qwen3.6-35B-A3B NVFP4, ~15 s reading the "
                  "checkpoint into memory, the 20.9 GiB `tensorfold pull` if it is not there (yours to run), evicts "
                  f"{MODEL}")
        dense = place.answer(h, {"lane": "worker", "model": "qwen3.8:27b"})
        ctx.check(f"a model TensorFold does not name is out, got {dense['verdict']!r}", dense["fits"] is False
                  and "TensorFold serves the models its table names" in dense["verdict"])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
