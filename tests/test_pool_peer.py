"""tests.test_pool_peer -- Halo 3.3.8.0 R3 deliverable 9: the pool through the host to its peers (local_pool/peer.py,
host/routes_view.View.catalog's `pool`, providers/huggingface.resolve_huggingface_local_server's fallback), over
tests/helpers/host_act_rig.PeerRig (the controller is the host machine, `pc-host`; this process's home is a paired
peer); no model call, never a request beyond 127.0.0.1:

1. the host's catalog serves the `pool` entry and its key (from the env var the entry names) to a paired peer; a
   peer's `hf:local/<model>@pool` resolves to the controller's LAN address with that key and the fit's max_ctx;
2. an unpaired machine gets nothing: a request signed with a key the host never paired is refused, and a home with
   no paired host resolves no pool; a host whose config has no pool entry offers none.
Run: python -m tests.test_pool_peer
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.host_act_rig import PeerRig  # noqa: E402
from tests.helpers.pool_rig import PoolHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
QWEN = "qwen3-next-80b-a3b-q4km"
ENV = "HALO_SECRET_POOL_TEST_KEY"


def _host_pool(home: Path) -> None:
    cfg_p = home / "config.json"
    cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
    cfg.setdefault("huggingface", {})["local_servers"] = [
        {"name": "pool", "url": "http://192.0.2.10:8090/v1", "api_key_env": ENV, "max_ctx": 32768, "model": QWEN,
         "members": ["pc", "worker1"], "cache": "f16", "runtime": "llama-server", "pool": True}]
    cfg_p.write_text(json.dumps(cfg), encoding="utf-8")


@test
def test_a_paired_peer_sees_the_entry_and_the_key(ctx: Ctx):
    from halo_harness.local_pool import peer
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    with PeerRig() as rig:
        _host_pool(rig.home)
        os.environ[ENV] = "a-generated-key-for-the-test"
        try:
            peer.reset()
            st, got = 200, rig.client().catalog(4096)
            offer = got.get("pool") or {}
            ctx.check(f"the host's catalog serves the entry and the key, got {offer}", offer.get("url") ==
                      "http://192.0.2.10:8090/v1" and offer.get("api_key") == "a-generated-key-for-the-test"
                      and offer.get("max_ctx") == 32768 and offer.get("members") == ["pc", "worker1"])
            s = resolve_huggingface_local_server("pool")
            ctx.check(f"the peer's hf:local/...@pool resolves to the controller's LAN address, got {s}", s is not None
                      and s.url == "http://192.0.2.10:8090/v1" and s.api_key == "a-generated-key-for-the-test"
                      and s.max_ctx == 32768 and s.runtime == "llama-server")
            from halo_harness.providers.huggingface_local_resolve import resolve_local_server
            r = resolve_local_server("pool", model=QWEN)
            ctx.check(f"the session's resolver too, got {r}", r is not None and r.base_url == "http://192.0.2.10:8090/v1"
                      and r.api_key == "a-generated-key-for-the-test")
        finally:
            os.environ.pop(ENV, None)
            peer.reset()
        ctx.check(f"nothing left 127.0.0.1, got {rig.rig.blocked}", not rig.rig.blocked)


@test
def test_an_unpaired_machine_gets_nothing(ctx: Ctx):
    from halo_harness.local_pool import peer
    from halo_harness.ollama_steward.host_client import HostClient, HostError
    from halo_harness.providers.huggingface import resolve_huggingface_local_server
    with PeerRig() as rig:
        _host_pool(rig.home)
        os.environ[ENV] = "a-generated-key-for-the-test"
        try:
            entry = dict(rig.client().entry)
            stranger = HostClient(entry, b"0" * 32, "f" * 32)
            try:
                stranger.catalog(4096)
                refused = ""
            except HostError as e:
                refused = f"{e.status} {e}"
            ctx.check(f"a machine the host never paired is refused, got {refused!r}", refused.startswith(("401", "403")))
        finally:
            os.environ.pop(ENV, None)
    with PoolHome():
        peer.reset()
        ctx.check("a home with no paired host resolves no pool", resolve_huggingface_local_server("pool") is None)
    with PeerRig() as rig:
        peer.reset()
        ctx.check(f"a host with no pool entry offers none, got {rig.client().catalog(4096).get('pool')}",
                  rig.client().catalog(4096).get("pool") is None and resolve_huggingface_local_server("pool") is None)
        peer.reset()


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
