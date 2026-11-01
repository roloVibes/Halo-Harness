"""tests.test_host_refresh_pool -- Halo 3.3.8.0 R4 deliverable 5: the off-hours refresh re-benches the pool
(host/refresh_pool.py; host/refresh_plan.plan's pool row; host/refresh.tick; `halo host refresh status`), over
tests/helpers/pool_run_rig.RunRig (the pool runs on the fake llama-server; the battery's answers come from a runner):

1. the plan gains the pool's row while it runs and has no card ("unverified"), `halo host refresh status` says when
   ("once every member has been idle 20 min");
2. a call through the pool or a busy member keeps it waiting (one line naming the member);
3. the tick runs the pool's quick bench, the card is stamped verified by the host, the refresh log's line says the
   measured figure; after it the card is fresh and the row is gone.
Run: python -m tests.test_host_refresh_pool
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.pool_run_rig import QWEN, RunRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_pool_bench import Runner  # noqa: E402

test, TESTS = new_registry()


@test
def test_the_pool_is_re_benched_when_every_member_is_idle(ctx: Ctx):
    from halo_harness.host import refresh as R, refresh_pool as RP
    from halo_harness.host.refresh_plan import plan, settings
    from halo_harness.local_pool import bench
    from halo_harness.local_pool.catalog import get
    from halo_harness.local_pool.speed import card_for
    from halo_harness.local_refresh_cli import cmd_host_refresh
    from halo_harness.ollama_steward import changes_pool
    from halo_harness.ollama_steward.ledger import append_lines
    from tests.helpers.steward_seed import line
    with RunRig() as rig:
        ctx.check("no pool running: no row", RP.row(rig.peer) is None)
        changes_pool.warm(QWEN, state_dir=rig.peer, by="test")
        p = plan(rig.peer, [], settings_=settings(rig.peer))
        row = next((r for r in p["rows"] if r.get("pool")), None)
        ctx.check(f"the plan gains the pool's row, got {row}", row is not None and row["host"] == "pool"
                  and row["why"] == "unverified" and row["bench"] and not row["battery"] and row["seconds"] > 0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            cmd_host_refresh(["status"])
        out = buf.getvalue()
        ctx.check(f"halo host refresh status says when, got {out!r}",
                  f"the pool: re-bench {QWEN} (~" in out and "once every member has been idle 20 min" in out)
        RP.SEAMS["idle"] = lambda p: {"busy": "a model is loading" if p["member"] == "pc" else "", "idle_s": 9999}
        try:
            got = RP.members_idle(rig.peer, idle_min=20)
            ctx.check(f"a busy member keeps it waiting, named, got {got['line']!r}", not got["ok"]
                      and "pc: busy -- a model is loading" in got["line"])
            RP.SEAMS["idle"] = lambda p: {"busy": "", "idle_s": 9999}
            append_lines(rig.peer, [line(host={"name": "pool", "url": "x"}, model=QWEN, dialect="openai", ago=30.0)])
            got = RP.members_idle(rig.peer, idle_min=20)
            ctx.check(f"a call through the pool keeps it waiting, got {got['line']!r}", not got["ok"]
                      and got["line"] == "the pool answered a call within 20 min: it waits")
            (rig.peer / "ollama" / "traffic.jsonl").unlink()
            ran = []
            said = R.tick(rig.peer, [], force=True, start=lambda fn: (ran.append(1), fn()),
                          runners={"pool_bench": lambda **kw: bench.bench(send=Runner(), **kw)})
        finally:
            RP.SEAMS.clear()
        card = card_for(get(QWEN), rig.peer) or {}
        end = next((x for x in reversed(R.log(rig.peer)) if x.get("kind") == "end"), {})
        ctx.check(f"the tick ran the pool's quick bench, stamped by the host, got {said!r} {end.get('line')!r}",
                  ran and said == f"refresh: {QWEN} on pool (unverified)" and end.get("ok") and end.get("pool")
                  and card.get("verified_by") == "the host" and [w["window"] for w in card["windows"]] == [32768]
                  and "its speed card verified by the host -- 11.2 tok/s measured" in end["line"])
        st = R.status(rig.peer, [])
        ctx.check(f"after it: fresh, no row, got {st['pool_line']!r}", not [r for r in st["plan"]["rows"] if r.get("pool")]
                  and st["pool_line"].startswith("the pool: its speed card is fresh (11.2 tok/s measured"))
        changes_pool.stop(state_dir=rig.peer, by="test")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
