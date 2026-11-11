"""tests.test_engines_peer_rows -- what a paired host's rows can make this machine do (Halo 3.3.14.0 R2;
engines/peer.py, local_sched/place_advice.py, host/join.py):

1. REVIEW #40 (LOCAL-6): an engine offer is always reached on the paired host's own address; an offer whose runtime
   word is not an engine id is skipped (said once), never followed to the url it names;
2. REVIEW #41 (LOCAL-7): a peer row with a port that is not a whole number 1-65535 is dropped: `peer.hosts` and
   `place_advice.candidates` answer without it (the join stores rows through the same `port_of`).
Every address is 192.0.2.x (documentation only); nothing is sent anywhere.
Run: python -m tests.test_engines_peer_rows"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.engine_home import EngineHome  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
HOST = {"name": "box", "url": "http://192.0.2.10:7450", "state": "joined"}


class _Patched:
    """fleet.store / identity / HostClient answering from fixtures for the length of a block."""

    def __init__(self, hosts: list, catalog: dict) -> None:
        self.hosts, self.catalog = hosts, catalog

    def __enter__(self):
        from halo_harness.peers import identity, store
        from halo_harness.ollama_steward import host_client
        cat = self.catalog

        class Client:
            def __init__(self, *_a) -> None:
                pass

            def catalog(self, *_a):
                return cat
        self.saved = (store.hosts, store.key_for, identity.harness, host_client.HostClient)
        store.hosts = lambda home=None: list(self.hosts)
        store.key_for = lambda e, home=None: b"fixture-pair-key"
        identity.harness = lambda *a, **k: {"id": "fixture-harness"}
        host_client.HostClient = Client
        return self

    def __exit__(self, *exc):
        from halo_harness.engines import peer
        from halo_harness.peers import identity, store
        from halo_harness.ollama_steward import host_client
        store.hosts, store.key_for, identity.harness, host_client.HostClient = self.saved
        peer.reset()


@test
def test_an_offer_is_reached_on_the_hosts_own_address(ctx: Ctx):
    from halo_harness.engines import peer
    with EngineHome():
        offer = {"url": "http://192.0.2.99:9000/v1", "runtime": "tensorfold", "model": "m", "api_key": "k"}
        with _Patched([HOST], {"engines": {"tensorfold": offer}}):
            got = peer._ask("tensorfold")
            ctx.check(f"the url is moved to the host's address, got {got}", got and got["url"].startswith(
                "http://192.0.2.10:9000") and got["runtime"] == "tensorfold")
        foreign = {**offer, "runtime": "llama-server"}
        with _Patched([HOST], {"engines": {"tensorfold": foreign}}):
            with warnings.catch_warnings(record=True) as said:
                warnings.simplefilter("always")
                got = peer._ask("tensorfold")
                again = peer._ask("tensorfold")
            ctx.check(f"a runtime word that is no engine id: skipped, got {got} {again}", got is None and again is None)
            lines = [str(w.message) for w in said]
            ctx.check(f"said once, got {lines}", len(lines) == 1 and "'llama-server', not an engine id: skipped" in lines[0])
            ctx.check("remote_entry has nothing to call", peer.remote_entry("tensorfold") is None)


@test
def test_a_peer_row_with_a_bad_port_is_dropped(ctx: Ctx):
    from halo_harness.engines import peer
    from halo_harness.local_sched.place_advice import candidates
    with EngineHome() as h:
        rows = [{"runtime": "tensorfold", "addr": "192.0.2.10", "port": "80a"},
                {"runtime": "freetoken", "addr": "192.0.2.10", "port": 1919},
                {"runtime": "strata", "addr": "192.0.2.10", "port": 70000}]
        host = {**HOST, "servers": rows, "serves": [{"addr": "192.0.2.10", "port": "x11434"},
                                                    {"addr": "192.0.2.11", "port": 11434, "name": "ollama-b"}]}
        with _Patched([host], {}):
            got = peer.hosts(h.state)
            ctx.check(f"hosts() answers without the bad rows, got {got}", [x.engine for x in got if not x.local] == ["freetoken"])
            names = [c.name for c in candidates(h.state)]
            ctx.check(f"placement's candidates answer, got {names}", "ollama-b" in names and "box" in names)
        ctx.check("port_of: words, bools and out-of-range ports are None", [peer.port_of(v) for v in
                  ("80a", True, 0, 65536, "443", 8080)] == [None, None, None, None, 443, 8080])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
