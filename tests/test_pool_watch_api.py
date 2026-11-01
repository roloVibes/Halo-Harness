"""tests.test_pool_watch_api -- Halo 3.3.8.0 R4 deliverable 8, the API half: Local -> Pool's measured half
(studio/pool_watch_api.py: GET/POST local/pool/bench, GET local/pool/findings), each member's claims by bundle on the run
route, and the Pack Manager's bundle fields (GET pack/bundles: big-reasoner's parts), over
tests/helpers/pool_run_rig.RunRig (the controller's llama-server the loopback fake; no model loads):

1. GET local/pool/bench: the cost line first (seconds, the members busy), extrapolated until a card; POST runs the
   battery in the background (202), the GET then carries the card, the measured penalty line; a second POST while one
   runs, or with the pool stopped, is one line (409);
2. GET local/pool/findings: an RPC backend lost in the controller's log -> pool-degraded, keyed pool|<model>;
3. GET local/pool/run: each member's claim names its bundle, every claim on that card listed;
4. GET pack/bundles: big-reasoner with its pool part, its reservations' hosts and its priority.
Run: python -m tests.test_pool_watch_api
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _wait_bench(rig, timeout: float = 20.0) -> dict:
    end = time.monotonic() + timeout
    while True:
        _s, got = rig.studio("GET", "local/pool/bench")
        if not (got.get("bench") or {}).get("busy") or time.monotonic() > end:
            return got
        time.sleep(0.1)


@test
def test_the_bench_route(ctx: Ctx):
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        status, got = rig.studio("POST", "local/pool/bench", {})
        ctx.check(f"the pool stopped: one line, 409, got {status} {got}", status == 409
                  and got["error"].startswith("the pool is not running: Warm it first"))
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        status, got = rig.studio("GET", "local/pool/bench")
        ctx.check(f"the cost line first, extrapolated, got {status} {got.get('estimate')} {got.get('speed')}",
                  status == 200 and got["estimate"]["line"].startswith("local: ~") and "(pc, me: their GPUs are busy for "
                  "it)" in got["estimate"]["line"] and got["card"] is None and got["speed"]["measured"] is False
                  and got["cli"] == "halo local bench --host pool")
        status, got = rig.studio("POST", "local/pool/bench", {"quick": True})
        ctx.check(f"POST: 202, in the background, got {status} {got}", status == 202 and got["busy"]
                  and got["cli"] == "halo local bench --host pool --quick")
        again = rig.studio("POST", "local/pool/bench", {})
        done = _wait_bench(rig)
        ctx.check(f"a second POST while it runs is one line (or it had finished), got {again}",
                  again[0] in (409, 202))
        ctx.check(f"the card and the measured line, got {done.get('card')} {done.get('speed')}", done["card"]
                  and done["card"]["model"] == QWEN and done["card"]["lines"][0].startswith("pool speed card (the bench,")
                  and done["speed"]["measured"] and done["speed"]["word"].startswith("11.2 tok/s measured")
                  and done["bench"]["ok"] is True and any("32k: prompt" in x for x in done["bench"]["lines"]))
        changes_pool.stop(state_dir=rig.peer, by="test")


@test
def test_findings_run_claims_and_bundles(ctx: Ctx):
    from halo_harness.local_pool import launch
    from halo_harness.ollama_steward import changes_pool, server_log_hf, servers_hf
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        status, run = rig.studio("GET", "local/pool/run")
        pc = next(m for m in run["members"] if m["name"] == "pc")
        ctx.check(f"each member's claim names its bundle, the card's claims listed, got {pc['claim']}", status == 200
                  and pc["claim"]["bundle"] == f"pool:{QWEN}" and f"claimed by pool:{QWEN}" in pc["claim"]["line"]
                  and any(c["bundle"] == f"pool:{QWEN}" for c in pc["claim"]["claims"]))
        r = launch.run(rig.peer)
        with open(r["log"], "a", encoding="utf-8") as f:
            f.write(f"Failed to connect to 127.0.0.1:{rig.rpc_port}\n")
        s = next(x for x in servers_hf.roster(rig.peer) if x.name == "pool")
        server_log_hf.scan(rig.peer, s, from_start=True)
        status, got = rig.studio("GET", "local/pool/findings")
        rows = got.get("findings") or []
        ctx.check(f"pool-degraded, keyed pool|<model>, got {status} {rows}", status == 200 and any(
            f["rule"] == "pool-degraded" and f["key"] == f"pool|{QWEN}" and "degraded (pc down)" in f["finding"]
            for f in rows) and got["cli"] == "halo ollama steward findings")
        status, hosts = rig.studio("GET", "ollama/hosts")
        pool = next((s for s in hosts.get("local_servers") or [] if s["name"] == "pool"), {})
        ctx.check(f"the Steward page's rows carry it under the pool, got {[f['rule'] for f in pool.get('findings') or []]}",
                  status == 200 and any(f["rule"] == "pool-degraded" for f in pool.get("findings") or []))
        changes_pool.stop(state_dir=rig.peer, by="test")
        status, got = rig.studio("GET", "pack/bundles")
        big = next((b for b in got.get("bundles") or [] if b["id"] == "big-reasoner"), {})
        v = big.get("verdict") or {}
        ctx.check(f"big-reasoner: its pool part, its reservations' hosts, its priority, got {v.get('parts')} "
                  f"{v.get('claims')}", status == 200 and [p["host"] for p in v.get("parts") or []] == ["pool"]
                  and [x["host"] for x in v["claims"]["reservations"]] == ["pool", None]
                  and v["claims"]["priority"] == "high" and v.get("main_says"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
