"""tests.test_pool_bench -- Halo 3.3.8.0 R4 deliverable 1: the pool's speed card (local_pool/bench.py,
local_pool/speed.py; `halo local bench --host pool`), over tests/helpers/pool_run_rig.RunRig (the controller's
llama-server is tests/helpers/fake_llama_server.py on 127.0.0.1: it loads no model and answers with arithmetic):

1. the battery: the runner seam answers it (one untimed warm-up per window, a ~60 % prompt and a 256-token reply,
   the reserve 128 / 256 / 512); the card is written (host pool, cache key pool|<model>, the members, the split, each
   member's RTT, the cache, -c, the cold load from the launch); the cost line first, in seconds;
2. the recommendation row, `route` and `place.solve` flip from extrapolated to measured; with a single node's bench
   card of the same model the penalty is measured against it ("-38 % vs pc alone (it spills to the CPU there)");
   the auto-revert's baseline is the pool's own card;
3. the real sender through the fake's HTTP with the pool's key; it waits (one line, nothing sent) while the pool
   answered a call in the last minute or is not running; `halo local bench --host pool --quick --yes`.
Run: python -m tests.test_pool_bench
"""
from __future__ import annotations

import io
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


class Runner:
    """The battery's answers: 11.2 tok/s decode, 400 tok/s prompt; a reply of 128 or fewer tokens is cut."""

    def __init__(self, tok_s: float = 11.2) -> None:
        self.calls, self.tok_s = [], tok_s

    def __call__(self, messages: list, *, num_predict: int) -> dict:
        text = "".join(p.get("text", "") for m in messages for p in (m["content"] if isinstance(m["content"], list) else []))
        n_in = max(1, len(text) // 4)
        n = num_predict if num_predict <= 128 else 200
        self.calls.append((n_in, num_predict))
        return {"prompt_eval_count": n_in, "prompt_eval_duration": int(n_in / 400 * 1e9), "eval_count": n,
                "eval_duration": int(n / self.tok_s * 1e9), "done_reason": "length" if num_predict <= 128 else "stop"}


@test
def test_the_battery_writes_the_pools_card(ctx: Ctx):
    from halo_harness.local_pool import bench, launch
    from halo_harness.local_pool.catalog import get
    from halo_harness.local_pool.speed import card_for, figures
    from halo_harness.ollama_steward import changes_pool
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        before = figures(get(QWEN), rig.peer, launch.run(rig.peer))
        ctx.check(f"no card: extrapolated, said, got {before['word']!r}", not before["measured"]
                  and before["word"] == "30-45 tok/s extrapolated (no pool speed card yet: halo local bench --host pool)")
        est = bench.estimate(state_dir=rig.peer)
        ctx.check(f"the cost line in seconds, the members busy, got {est}", est["windows"] == [8192, 32768]
                  and est["line"].startswith(f"local: ~{est['seconds']} s on the pool (pc, me: their GPUs are busy for "
                                             "it), writes the pool's speed card; no tokens leave the LAN"))
        run, lines = Runner(), []
        c = bench.bench(send=run, state_dir=rig.peer, on_line=lines.append)
        timed = [run.calls[1], run.calls[3]]
        ctx.check(f"a warm-up then a timed call per window, then the reserve, got {run.calls}", c["ok"]
                  and [x[1] for x in run.calls] == [8, 256, 8, 256, 128, 256] and len(timed) == 2
                  and all(abs(n / (w * 0.6) - 1) < 0.05 for (n, _p), w in zip(timed, (8192, 32768))))
        w8, w32 = c["windows"]
        ctx.check(f"measured tok/s and TTFT per window, got {w8} {w32}", w8["tok_s"] == 11.2 == w32["tok_s"]
                  and w8["prompt_tok_s"] == 400.0 and w8["ttft_ms"] < w32["ttft_ms"] and c["reserve_floor"] == 256)
        r = launch.run(rig.peer)
        ctx.check(f"the card: host pool, the members, the split, the RTT, the cold load, got "
                  f"{ {k: c.get(k) for k in ('host', 'members', 'split', 'cache', 'ctx', 'cold_load_s', 'rpc')} }",
                  c["host"] == "pool" and c["digest"] == f"pool|{QWEN}" and c["members"] == ["pc", "me"]
                  and c["split"] == r["split"] and c["cache"] == "f16" and c["ctx"] == 32768
                  and c["cold_load_s"] == r["ready_s"] and isinstance(c["cold_load_s"], float)
                  and [x["member"] for x in c["rpc"]] == ["pc"] and "rtt_ms" in c["rpc"][0])
        stored = card_for(get(QWEN), rig.peer) or {}
        ctx.check(f"the card is in the speed-card store, got {stored.get('host')} {stored.get('model')}",
                  stored.get("host") == "pool" and stored.get("model") == QWEN and stored.get("pool") is True)
        ctx.check(f"one line per window as it lands, got {lines}", any(x.startswith("32k: prompt 400 tok/s") for x in lines)
                  and any("warming" in x for x in lines))


@test
def test_the_recommendation_route_and_place_flip_to_measured(ctx: Ctx):
    from halo_harness.local_pool import bench
    from halo_harness.local_pool.budget import budgets
    from halo_harness.local_pool.catalog import get
    from halo_harness.local_pool.recommend import verdict
    from halo_harness.local_pool.route import pool_host, route
    from halo_harness.local_sched.place import solve
    from halo_harness.ollama_steward import changes_pool
    from halo_harness.providers.local_bench_runs import save
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        v0 = verdict(QWEN, budgets(state_dir=rig.peer), state_dir=rig.peer)
        ctx.check(f"before: extrapolated, got {v0['speed_word']!r}", v0["speed"]["measured"] is False
                  and "extrapolated" in v0["speed_word"])
        bench.bench(send=Runner(), state_dir=rig.peer)
        v1 = verdict(QWEN, budgets(state_dir=rig.peer), state_dir=rig.peer)
        ctx.check(f"after: measured, the research's penalty said, got {v1['speed_word']!r}", v1["speed"]["measured"]
                  and v1["speed_word"].startswith("11.2 tok/s measured (against one node: the research's -38 %"))
        save(rig.peer, {"digest": "sha256:c0de", "host": "pc", "model": "qwen3-next:80b", "at": time.time(),
                        "windows": [{"window": 16384, "tok_s": 18.0, "on_gpu": False}]})
        v2 = verdict(QWEN, budgets(state_dir=rig.peer), state_dir=rig.peer)
        ctx.check(f"a single node's card: the penalty measured against it, got {v2['speed_word']!r}",
                  v2["speed_word"] == "11.2 tok/s measured, -38 % vs pc alone (it spills to the CPU there)"
                  and v2["speed"]["penalty_pct"] == 38.0 and v2["speed"]["vs"] == "pc")
        a = route({"model": QWEN}, state_dir=rig.peer)
        ctx.check(f"route: measured, its penalty, got {a.get('verdict')!r} {a.get('penalty_pct')}", a["now"]
                  and a["measured"] and a["penalty_pct"] == 38.0 and "pool: 11.2 tok/s measured, -38 % vs pc alone"
                  in a["verdict"])
        plan = solve([{"lane": "reasoner", "model": QWEN, "host": "pool"}], hosts=[pool_host(rig.peer)],
                     state_dir=rig.peer)
        row = plan["rows"][0]
        ctx.check(f"place.solve: the measured line in the score's why, got {row['why']!r} {row['score']}",
                  row["host"] == "pool" and "pooled: 11.2 tok/s measured, -38 % vs pc alone" in row["why"])
        b = changes_pool.baseline(get(QWEN), rig.peer)
        ctx.check(f"the auto-revert's baseline: the pool's own card, got {b}", b and b["own"] and b["tok_s"] == 11.2
                  and b["host"] == "pool")


@test
def test_the_real_sender_the_waits_and_the_cli(ctx: Ctx):
    from halo_harness.local_bench_cli import cmd_bench
    from halo_harness.local_pool import bench
    from halo_harness.ollama_steward import changes_pool
    from halo_harness.ollama_steward.ledger import append_lines
    from tests.helpers.steward_seed import line
    with RunRig() as rig:
        got = bench.bench(send=Runner(), state_dir=rig.peer)
        ctx.check(f"not running: one line, nothing sent, got {got}", not got["ok"]
                  and got["say"].startswith("the pool is not running: Warm it first"))
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        c = bench.bench(quick=True, state_dir=rig.peer)
        ctx.check(f"the real sender through the fake's HTTP with the key: -c alone (quick), got {c.get('windows')}",
                  c["ok"] and [w["window"] for w in c["windows"]] == [32768] and c["windows"][0]["tok_s"] == 11.2
                  and c["reserve_floor"] == 256)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cmd_bench(["--host", "pool", "--quick", "--yes"])
        out = buf.getvalue().splitlines()
        ctx.check(f"halo local bench --host pool: the cost line first, the card, the pool's word, got {out}", rc == 0
                  and out[0].startswith("local: ~") and " s on the pool (pc, me:" in out[0]
                  and any(x.strip().startswith("pool speed card (the bench,") for x in out)
                  and out[-1].strip().startswith("pool: 11.2 tok/s measured"))
        append_lines(rig.peer, [line(host={"name": "pool", "url": "x"}, model=QWEN, dialect="openai", ago=5.0)])
        busy = bench.bench(send=Runner(), state_dir=rig.peer)
        ctx.check(f"a call in the last minute: it waits, got {busy.get('say')!r}", not busy["ok"]
                  and busy["say"].startswith("the pool answered a call within the last 60 s"))
        changes_pool.stop(state_dir=rig.peer, by="test")
        from halo_harness.local_pool.budget import budgets
        rows = {r["name"]: r for r in budgets(state_dir=rig.peer)}
        ctx.check(f"each member row says which spoke for its link (the OS's adapter before the RTT), got "
                  f"{ {k: v.get('spoke') for k, v in rows.items()} }", all(str(r.get("spoke")).startswith(
                      ("the OS (its adapter)", "the probe (an RTT)", "nothing yet")) for r in rows.values()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
