"""tests.test_pool_route -- Halo 3.3.8.0 R3 deliverable 6: the pool answers `route` like a host and sits in
place.solve as one more option (local_pool/route.py, local_sched/place.py), and the window truth clamps to the pool
entry's max_ctx (agent/model_window.window_of, providers/hf_profile.window); over tests/helpers/pool_run_rig.RunRig:

1. route: a catalog model that fits the pool (not running: Warm starts it, the load seconds from the GGUF and the
   rate), the research's penalty; a model the pool does not serve; a window past the pool's; running: warm and now;
   a worker down: degraded, no lane;
2. place.solve: the pool is scored with its penalty (38) and loses to a single node that holds the model; with no
   such node it takes the lane; `halo local place` says the pool's line;
3. a request that asks for 65,536 on hf:local/...@pool gets the fit's 32,768, its reason named.
Run: python -m tests.test_pool_route
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_route_answers_like_a_host(ctx: Ctx):
    from halo_harness.local_pool.route import PENALTY_PCT, route
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        a = route({"model": "qwen3-next:80b", "window": 32768}, state_dir=rig.peer)
        ctx.check(f"fits the pool, not running: Warm starts it, the load seconds said, got {a}", a["host"] == "pool"
                  and a["fits"] is True and a["now"] is False and a["installed"] is True and a["load_s"] == 33
                  and a["penalty_pct"] == PENALTY_PCT == 38.0 and a["verdict"].startswith(
                      "Qwen3-Next-80B-A3B Q4_K_M fits the pool (2 nodes, 32k F16 / 32k Q8_0); Warm starts it, ~33 s"))
        a = route({"model": "qwen3.8:27b"}, state_dir=rig.peer)
        ctx.check(f"a model the pool does not serve, got {a['verdict']!r}", a["fits"] is False
                  and a["verdict"].startswith("the pool serves its catalog models (qwen3-next-80b-a3b-q4km"))
        a = route({"model": QWEN, "window": 65536}, state_dir=rig.peer)
        ctx.check(f"a window past the pool's, got {a['verdict']!r}", a["fits"] is False
                  and a["verdict"] == "Qwen3-Next-80B-A3B Q4_K_M fits the pool up to 32k (Q8_0 KV); 65,536 is past it")
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        a = route({"model": QWEN}, state_dir=rig.peer)
        ctx.check(f"running: warm, now, got {a}", a["fits"] and a["now"] and a["warm"] and a["window"] == 32768
                  and "runs on the pool now (f16 KV, -c 32,768)" in a["verdict"])
        rig.fake.kill_all()  # pc's rpc-server goes away
        a = route({"model": QWEN}, state_dir=rig.peer)
        ctx.check(f"a worker down: degraded, no lane, got {a}", a["fits"] is False and a["degraded"] == ["pc"]
                  and a["verdict"].startswith("the pool is degraded (pc down)"))


@test
def test_the_pool_in_place_solve(ctx: Ctx):
    from halo_harness.local_pool.route import PoolHost
    from halo_harness.local_sched.place import answer, solve
    pc = SimpleNamespace(name="pc", url="http://192.0.2.10:11434")
    lanes = [{"lane": "main", "model": "qwen3.8:27b", "host": "pc"}, {"lane": "reasoner", "model": "qwen3-next:80b",
                                                                       "host": "pc"}]
    with RunRig() as rig:
        def ask(h, ln):
            if getattr(h, "pool", False):
                return answer(h, ln, state_dir=rig.peer)
            big = ln["model"] == "qwen3-next:80b"
            return {"host": h.name, "via": "host", "fits": True, "now": not big, "warm": not big, "evicts": [],
                    "load_s": 40.0 if big else None, "installed": True, "capable": True, "need_bytes": 10, "usable_bytes": 100,
                    "verdict": "fits"}
        plan = solve(lanes, hosts=[pc, PoolHost()], answers=ask, claims={})
        row = next(r for r in plan["rows"] if r["lane"] == "reasoner")
        ctx.check(f"a single node holds it: it wins over the pool (the penalty), got {row}", row["host"] == "pc")
        def ask_none(h, ln):
            got = ask(h, ln)
            return {**got, "fits": False, "verdict": "does not fit (needs 53.6 of 22.0 GB)"} \
                if not getattr(h, "pool", False) and ln["model"] == "qwen3-next:80b" else got
        plan = solve(lanes, hosts=[pc, PoolHost()], answers=ask_none, claims={})
        row = next(r for r in plan["rows"] if r["lane"] == "reasoner")
        ctx.check(f"no node holds it: the pool takes the lane, its penalty said, got {row}", row["host"] == "pool"
                  and "pooled: -38 % decode" in row["why"] and row["moved"] is True)
        from halo_harness.local_place_cli import place_lineup
        got = place_lineup()
        ctx.check(f"halo local place says the pool, got {got.get('pool')!r}", got.get("pool") == "the pool is not running")


@test
def test_the_window_clamps_to_the_pools_fit(ctx: Ctx):
    from halo_harness.agent.model_window import window_of
    from halo_harness.providers.hf_profile import window
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        ref = SimpleNamespace(provider="huggingface", model=QWEN, host="pool", local=True, mlx=False,
                              raw=f"hf:local/{QWEN}@pool")
        w = window_of(ref, state_dir=rig.peer, readers={"props": lambda r: 65536, "loaded": lambda r: 65536})
        ctx.check(f"asked 65,536: the fit's 32,768, its reason named, got {w}", w["tokens"] == 32768
                  and w["source"] == "the pool's fit (max_ctx)")
        ctx.check(f"the request clamp says the same, got {window(ref, 65536)}", window(ref, 65536) == 32768
                  and window(ref, 16384) == 16384)
        w = window_of(ref, state_dir=rig.peer, readers={"props": lambda r: None, "loaded": lambda r: None,
                                                         "trained": lambda r: None})
        ctx.check(f"nothing loaded yet: the entry's max_ctx, got {w}", w["tokens"] == 32768 and w["source"] == "host max_ctx")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
