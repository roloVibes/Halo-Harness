"""tests.test_idle_busy -- Halo 3.3.7.0 R4: idle detection, foreign clients in the busy wait and the traffic view, and
the host's residency clock (ollama_steward/idle.py, providers/local_bench_busy.py, host/residency.py) over a fake
`/api/ps` on 127.0.0.1:0 (tests/helpers/sched_rig.SchedHome) and, for the clock, R2's PeerRig (a real halo host
serving a fake, this process the peer holding `control`):

1. a model in /api/ps that no Halo record explains is "a client that is not a halo": its name, size and since; the
   bench's busy wait says so; idle_since is busy; `halo ollama traffic` prints the foreign line;
2. a ledger call, a scheduler load, a speed card or a battery profile within 30 minutes explains it; idle_since is
   the newest use with a fake clock (never a sleep);
3. the residency clock: a pivot through the host writes it, GET residency answers it, and the peer's held_for reads it
   with its own clock empty; with no host, held_for is this process's own clock and the pivot line says so.
Nothing leaves 127.0.0.1; no model is called.
Run: python -m tests.test_idle_busy
"""
from __future__ import annotations

import contextlib
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.sched_rig import BIG, CODER, SchedHome, ps_row  # noqa: E402

test, TESTS = new_registry()


@test
def test_a_foreign_model_is_named_and_waited_for(ctx: Ctx):
    from halo_harness.ollama_steward.idle import foreign, foreign_line, idle_since
    from halo_harness.providers.local_bench_runs import busy
    with SchedHome(loaded=[ps_row(CODER, 17.3 * 1e9 / 2 ** 30)]) as h:
        rows = foreign(h.state, h.host)
        ctx.check(f"one foreign model with its size and since, got {rows}", len(rows) == 1 and rows[0]["model"] == CODER
                  and rows[0]["size_gb"] == 17.3 and rows[0]["since_text"])
        line = foreign_line(rows)
        ctx.check(f"the traffic line, got {line!r}", line.startswith("foreign: 1 model, 17.3 GB, since ")
                  and "a client that is not a halo" in line and "names the model, never the client" in line)
        why = busy(h.state, "pc", sessions=lambda: [])
        ctx.check(f"the bench waits for it, got {why!r}", why.startswith("a client that is not a halo holds "
                                                                      f"{CODER} (17.3 GB) on pc since "))
        idle = idle_since(h.state, h.host, sessions=lambda: [])
        ctx.check(f"idle_since is busy, got {idle['line']!r}", idle["busy"] and idle["idle_s"] == 0.0)
        first = rows[0]["since"]
        again = foreign(h.state, h.host, now=time.time() + 600)
        ctx.check("since stays the first time it was seen", abs(again[0]["since"] - first) < 1)
        from halo_harness.ollama_steward.cli import cmd_ollama_traffic
        h.loads(BIG, 30.0)  # one ledger line so the traffic view has a row for pc
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cmd_ollama_traffic(["--host", "pc"])
        ctx.check(f"halo ollama traffic prints the foreign line, got {out.getvalue()[-300:]!r}",
                  "foreign: 1 model, 17.3 GB" in out.getvalue())


@test
def test_halo_records_explain_a_loaded_model(ctx: Ctx):
    from halo_harness.local_sched.loads import record
    from halo_harness.ollama_steward.idle import explained, foreign, idle_since
    with SchedHome(loaded=[ps_row(CODER, 17.0), ps_row(BIG, 16.0)]) as h:
        h.loads(CODER, 25.0)  # a ledger line that paid a load, 60 s ago
        record(h.state, session=None, host="pc", model=BIG, seconds=0.0, why="refresh")
        ctx.check("a ledger call explains it", explained(h.state, "pc", CODER).startswith("a call from"))
        ctx.check("a scheduler load explains it", explained(h.state, "pc", BIG) == "the scheduler's refresh")
        ctx.check("nothing foreign", foreign(h.state, h.host) == [])
        later = time.time() + 3600
        ctx.check("an hour later the records no longer explain it", len(foreign(h.state, h.host, now=later)) == 2)
    with SchedHome(loaded=[]) as h:
        h.loads(CODER, 25.0)
        now = time.time() + 25 * 60
        idle = idle_since(h.state, h.host, sessions=lambda: [], now=now)
        ctx.check(f"idle 26 min after the last call (fake clock), got {idle}", idle["busy"] == ""
                  and 25 * 60 <= idle["idle_s"] <= 27 * 60 and "idle 26 min" in idle["line"])
        live = idle_since(h.state, h.host, sessions=lambda: [{"session_id": "s-9", "model": f"ol:{BIG}@pc", "pid": -1}])
        ctx.check(f"a session on the card is busy, got {live['busy']!r}", live["busy"].startswith("session s-9 is using"))


@test
def test_the_residency_clock_through_the_host(ctx: Ctx):
    from halo_harness.local_sched import pivot as P
    from halo_harness.providers.ollama import OllamaHost
    from tests.helpers.host_act_rig import PeerRig
    with PeerRig() as rig:
        rig.mock.ps_response = {"models": [ps_row(CODER, 18.0)]}
        host = OllamaHost(name="pc", url=rig.peer_url)
        gen = P.run(P.plan(host, CODER, BIG, window=32768), host=host)
        while True:
            try:
                next(gen)
            except StopIteration as stop:
                got = stop.value
                break
        from halo_harness.host.residency import rows
        mine = rows(rig.home)
        ctx.check(f"the host's clock has the model the pivot loaded, got {mine}", got["ok"] and mine
                  and mine[0]["model"] == BIG and mine[0]["op"] == "warm" and mine[0]["by"])
        st, ans = rig.get("residency")
        ctx.check(f"GET residency answers it, got {st} {ans}", st == 200 and ans["residency"][0]["model"] == BIG
                  and ans["min_resident_s"] == 60.0)
        P._SINCE.clear()  # another halo: its own clock is empty
        held = P.held_for(host, BIG)
        ctx.check(f"held_for reads the host's clock, got {held}", 55.0 <= held <= 60.0)
        ctx.check("the clock is named", P.clock_of(host) == "the host's residency clock")
    with SchedHome() as h:
        P.mark_loaded(h.host, CODER)
        ctx.check("with no host: this process's own clock, said so", P.held_for(h.host, CODER) > 55
                  and P.clock_of(h.host).startswith("this halo's own clock: no halo host serves pc"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
