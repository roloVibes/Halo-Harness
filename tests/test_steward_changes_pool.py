"""tests.test_steward_changes_pool -- Halo 3.3.8.0 R3 deliverable 7: the pool's warm and stop as changes under the
steward contract (ollama_steward/changes_pool.py, the rows in ollama_steward/changes.py), over
tests/helpers/pool_run_rig.RunRig; no model call:

1. warm and stop are change rows (key pool|<model>, field pool.state, host pool, before / after, the baseline in
   `why`); a second warm inside 10 minutes is one line with the minutes left, a stop is never held back;
2. the auto-revert: the pool's first three calls (ledger lines named `pool`) slower than the single-node bench card
   that holds the model -> the pool stops, both numbers said; with no such card the failures judge (half failed ->
   stopped; all fine -> kept);
3. `halo local changes revert <id>` of the warm stops the pool; a pool call's ledger line names `pool` as its host.
Run: python -m tests.test_steward_changes_pool
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


def _calls(rig, n: int, *, tok_s: float = 20.0, failed: int = 0) -> None:
    from halo_harness.local_pool.entry import current
    from halo_harness.ollama_steward.ledger import append_lines
    from tests.helpers.steward_seed import line
    url = (current() or {}).get("url")
    append_lines(rig.peer, [line(host={"name": "pool", "url": url}, model=QWEN, dialect="openai", eval_tok_s=tok_s,
                                 status=500 if i < failed else 200, ago=-1 - i * 0.01) for i in range(n)])


@test
def test_warm_and_stop_are_changes(ctx: Ctx):
    from halo_harness.ollama_steward import changes, changes_pool
    with RunRig() as rig:
        got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        rows = [r for r in changes.read(rig.peer) if r["field"] == "pool.state"]
        ctx.check(f"warm: one change row, got {rows}", got["ok"] and len(rows) == 1 and rows[0]["key"] == f"pool|{QWEN}"
                  and rows[0]["host"] == "pool" and (rows[0]["before"], rows[0]["after"]) == ("stopped", "running")
                  and "baseline: none (no single-node bench card holds this model here" in rows[0]["why"])
        ctx.check(f"the change line, got {changes.line_of(rows[0])!r}",
                  "pool.state stopped -> running on pool|" in changes.line_of(rows[0]))
        again = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        ctx.check(f"a second warm inside 10 min: one line, got {again['lines']}", not again["ok"] and again.get("cooldown")
                  and again["lines"][0].startswith("one pool change per 10 min: the last (running qwen3-next-80b-a3b-q4km)"
                                                   " was 0 min ago -- the next in 10 min"))
        done = changes_pool.stop(state_dir=rig.peer, by="test")
        rows = [r for r in changes.read(rig.peer) if r["field"] == "pool.state"]
        ctx.check(f"stop is never held back, its row, got {done['lines'][-1]!r}", done["ok"] and len(rows) == 2
                  and (rows[1]["before"], rows[1]["after"]) == ("running", "stopped"))


@test
def test_the_auto_revert(ctx: Ctx):
    from halo_harness.local_pool import launch
    from halo_harness.ollama_steward import changes_pool
    from halo_harness.providers.local_bench_runs import save
    with RunRig() as rig:
        save(rig.peer, {"digest": "sha256:c0de", "host": "pc", "model": "qwen3-next:80b", "at": time.time(),
                        "windows": [{"window": 16384, "tok_s": 60.0, "on_gpu": True}]})
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        ctx.check(f"the baseline is the single-node bench card, got {launch.run(rig.peer).get('baseline')}",
                  (launch.run(rig.peer).get("baseline") or {}).get("tok_s") == 60.0)
        _calls(rig, 2)
        ctx.check("two calls: still waiting", changes_pool.judge(rig.peer)["verdict"] == "waiting")
        _calls(rig, 1)
        j = changes_pool.judge(rig.peer)
        ctx.check(f"slower than the single node: reverted, both numbers said, got {j['line']!r}", j["verdict"] ==
                  "reverted" and j["line"] == "the pool's first 3 calls: 0 failed, median 20.0 tok/s against 60.0 tok/s "
                                             "on pc: worse -- the pool stopped" and launch.run(rig.peer) == {})
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        _calls(rig, 3, failed=2)
        j = changes_pool.judge(rig.peer)
        ctx.check(f"no baseline: two of three failed -> reverted, got {j['line']!r}", j["verdict"] == "reverted"
                  and "2 failed" in j["line"] and "(no single-node baseline)" in j["line"])
    with RunRig() as rig:
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        _calls(rig, 3)
        j = changes_pool.judge(rig.peer)
        ctx.check(f"no baseline, all fine: kept, got {j['line']!r}", j["verdict"] == "kept" and launch.alive(launch.run(rig.peer))
                  and changes_pool.judge(rig.peer)["verdict"] == "none")


@test
def test_a_revert_stops_and_the_ledger_names_the_pool(ctx: Ctx):
    from halo_harness.local_pool import entry, launch
    from halo_harness.ollama_steward import changes, changes_pool
    from halo_harness.ollama_steward.ledger_call import local_target
    with RunRig() as rig:
        got = changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        url = entry.current()["url"]
        req = SimpleNamespace(route=SimpleNamespace(provider="huggingface", dialect="openai-chat"),
                              creds=SimpleNamespace(base_url=url))
        ctx.check(f"a pool call's ledger line names the pool, got {local_target(None, req)}",
                  local_target(None, req)["host"] == {"name": "pool", "url": url})
        lines = changes.revert(rig.peer, got["change"]["id"], "reverted by hand")
        ctx.check(f"revert of the warm stops the pool, got {lines}", lines[0].startswith("put pool.state back to stopped")
                  and launch.run(rig.peer) == {} and entry.current() is None)
        other = SimpleNamespace(route=SimpleNamespace(provider="huggingface", dialect="openai-chat"),
                                creds=SimpleNamespace(base_url="http://127.0.0.1:8080/v1"))
        ctx.check("another server keeps its own name", local_target(None, other)["host"]["name"] == "127.0.0.1:8080")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
