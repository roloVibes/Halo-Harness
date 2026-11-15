"""tests.test_session_concurrency_gate -- the session's spawn cap (agent/subagent.SessionConcurrencyGate): with a limit
of two, a third spawn waits until a slot frees. (Kept from tests/test_teams_runtime.py when 3.6.0.0 R5d deleted
teams_runtime; this test never read a lineup.)
"""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()


@test
def test_max_parallel_cap_holds_the_third_spawn(ctx: Ctx):
    from halo_harness.agent.subagent import SessionConcurrencyGate
    gate = SessionConcurrencyGate(8)
    gate.set_limit(2)
    entered = []
    release = threading.Event()

    def worker(n):
        with gate:
            entered.append(n)
            release.wait(3.0)  # every holder stays inside until released

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    time.sleep(0.5)
    ctx.check(f"only two run concurrently, got {sorted(entered)}", len(entered) == 2)
    release.set()
    for t in threads:
        t.join(4.0)
    ctx.check(f"the third entered after a slot freed, got {sorted(entered)}", len(entered) == 3)
    ctx.check("the limit is readable back", gate.limit == 2)


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
