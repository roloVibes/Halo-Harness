"""tests.test_copilot_cost -- Copilot in the cost meter (Halo 3.3.17.0 R2, providers/copilot_cost.py): a `cp:work`
turn and a `copilot_ask` call add no dollars and mark the cost incomplete for `cp:work`; `/cost` and `/status` say
"+ Copilot: billed by your tenant (credits or licence)" (beside another unpriced model's line when there is one);
the status bar shows the priced part with its "+", or the token counts when nothing is priced -- never $0.00.

Run: python -m tests.test_copilot_cost
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.copilot_rig import CopilotRig  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
REASON = "Copilot: billed by your tenant (credits or licence)"


@test
def test_describe_cost_says_the_reason(ctx: Ctx):
    from halo_harness.model_display import describe_cost
    fig, line = describe_cost({"cost_usd": 0.0, "cost_complete": False, "cost_unknown": ["cp:work"]}, "cp:work")
    ctx.check(f"only Copilot, nothing priced: n/a and the reason, got {fig!r} {line!r}",
              fig == "n/a (no priced call yet)" and line == f"+ {REASON}")
    fig, line = describe_cost({"cost_usd": 0.42, "cost_complete": False, "cost_unknown": ["cp:work"]}, "or:a/b")
    ctx.check(f"a priced main and a Copilot tool call: the + and the reason, got {fig!r} {line!r}",
              fig == "$0.4200+" and line == f"+ {REASON}; this is what the priced agents spent")
    fig, line = describe_cost({"cost_usd": 1.0, "cost_complete": False, "cost_unknown": ["dbx:glm", "cp:work"]}, "dbx:glm")
    ctx.check(f"beside another unpriced model, got {line!r}",
              line == f"+ main's model glm reports no price; {REASON}; this is what the priced agents spent")
    fig, line = describe_cost({"cost_usd": 1.0, "cost_complete": False, "cost_unknown": ["dbx:glm"]}, "dbx:glm")
    ctx.check(f"no Copilot part: the 3.3.3.1 line unchanged, got {line!r}",
              line == "+ main's model glm reports no price; this is what the priced agents spent")


@test
def test_the_status_bar_is_never_zero_dollars(ctx: Ctx):
    from halo_harness.model_display import format_status_cost
    ctx.check("nothing priced: the token counts", format_status_cost(0.0, 1200, 300, complete=False) == "in 1k out 300")
    ctx.check("a priced part: its + ", format_status_cost(0.42, 0, 0, complete=False) == "$0.4200+")


@test
def test_meter_marks_and_a_cp_work_session(ctx: Ctx):
    from halo_harness import headless
    from halo_harness.model import CostMeter
    from halo_harness.model_display import describe_cost
    from halo_harness.providers.copilot_cost import mark_unpriced
    m = CostMeter(price_in=1e-6, price_out=2e-6)
    m.add_usage("openrouter", {"input_tokens": 1000, "output_tokens": 100}, model="or:a/b")
    mark_unpriced(m)
    mark_unpriced(m)
    f = m.cost_fields()
    ctx.check(f"a copilot_ask call: no dollars added, incomplete, cp:work named once, got {f}",
              abs(f["cost_usd"] - 0.0012) < 1e-9 and f["cost_complete"] is False and f["cost_unknown"] == ["cp:work"])
    mark_unpriced(None)  # no meter: nothing happens
    with CopilotRig() as r:
        r.signin()
        s = headless.build_session(cwd=REPO, model_ref_raw="cp:work", bare=True, print_mode=True, max_turns=2).session
        list(s.turn("who owns the budget"))
        f = s.cost_meter.cost_fields()
        ctx.check(f"a cp:work turn: incomplete for cp:work, $0 added, got {f}", f["cost_complete"] is False
                  and f["cost_unknown"] == ["cp:work"] and f["cost_usd"] == 0.0)
        fig, line = describe_cost(f, s.model_ref.raw)
        ctx.check(f"/cost says n/a and the reason, never $0.00, got {fig!r} {line!r}", "$0.00" not in fig
                  and line == f"+ {REASON}")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
