"""tests.test_soak_round -- Halo 2.0.6 round 9: the soak harness itself.

`tools/soak.py` is a manual/CI tool (10 minutes in CI, hours by hand);
this file pins that it WORKS -- a 30-second run through the real
controller + real TUI + mock upstream must pass every assertion the
long run makes (prompt-per-event, monotonic drain ticks, no traceback
in the log, phase lines settling, RSS bounded when psutil exists).

The round's own headline catch is pinned separately below: the
'governor' event kind. Round 4 emitted it and dispatch handled it, but
EVENT_KINDS never listed it, so the first real TUI run where the
Governor paced a 429 crashed the turn -- found by this soak, fixed in
halo_harness/events.py.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()


@test
def test_the_governor_event_kind_is_registered(ctx: Ctx):
    from halo_harness.events import EVENT_KINDS, Event
    ctx.check("'governor' is a valid event kind (the soak's catch: round 4 "
              "emitted and dispatched it, but EVENT_KINDS never listed it)",
              "governor" in EVENT_KINDS)
    ev = Event("governor", {"rate": 4.0, "rate_ceiling": 8.0, "cooldown_remaining": 2.0})
    ctx.check("constructing one no longer raises", ev.kind == "governor")


@test
def test_a_30_second_soak_passes(ctx: Ctx):
    from tools import soak
    rc = asyncio.run(soak.run_soak(30.0, json_out=False))
    ctx.check("the 30-second soak passes every assertion", rc == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
