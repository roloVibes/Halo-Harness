"""tests.test_plan_card_keys -- Halo 3.2.2.0 R4: the plan card shows its keys
FIRST, above the plan text, and caps the plan to the PendingDock's room
with a "... (N more lines; the plan file: <path>)" line -- a long plan used
to push `[1] [2] [3]` below the 12-line dock. Unit-level (no pilot): the
card renders its own text.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all

test, TESTS = new_registry()

KEYS = "[1] Approve, auto-accept edits · [2] Approve, manual · [3]/Esc Keep planning"


def _card(plan: str, path: str = "/home/kali/.claude/plans/amber-brook-kite.md"):
    from halo_harness.tui.widgets.cards import PlanCard
    return PlanCard(request_id="r1", input_data={"plan": plan, "path": path}, on_reply=lambda d: None)


def _lines(card) -> list:
    return str(card.render()).splitlines()


@test
def test_the_keys_line_is_the_first_line(ctx: Ctx):
    lines = _lines(_card("## Plan\n\n1. Read the parser\n2. Fix it"))
    ctx.check(f"first line is the keys, got {lines[:1]}", lines[0] == KEYS)
    ctx.check("the title follows", lines[1].endswith("Plan ready for review:"))
    ctx.check("a short plan is shown whole", lines[-1] == "2. Fix it")


@test
def test_a_long_plan_is_capped_with_the_plan_file_named(ctx: Ctx):
    from halo_harness.tui.widgets.cards import PlanCard
    plan = "\n".join(f"step {i}" for i in range(40))
    lines = _lines(_card(plan))
    ctx.check("the keys stay first", lines[0] == KEYS)
    ctx.check(f"capped to the dock's room (12 lines less the border), got {len(lines)}", len(lines) <= 11)
    shown = 40 - PlanCard.PLAN_MAX_LINES
    ctx.check(f"the overflow line names the rest and the file, got {lines[-1]!r}",
              lines[-1] == f"... ({shown} more lines; the plan file: /home/kali/.claude/plans/amber-brook-kite.md)")
    ctx.check("the full plan stays on the card for the `o` pager", _card(plan).plan_text.count("step") == 40)


@test
def test_an_answered_card_drops_the_keys(ctx: Ctx):
    card = _card("do it")
    card._on_reply = lambda d: None
    card.done = True
    card._refresh()
    ctx.check("no keys once answered", KEYS not in str(card.render()))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
