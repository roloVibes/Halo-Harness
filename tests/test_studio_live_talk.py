"""tests.test_studio_live_talk -- Session's Live column and the Conversations panel, 3.3.16.2 "agents talking" (the
owner: "so we see models conversing with each other and that's its own label"), in headless Chrome
(tests/helpers/studio_session_think.py `talk`, steps in tests/helpers/studio_session_talk.py; skipped without one):

1. Conversations is not open when Session loads;
2. a task is a TALK row: the speaker's tag, an arrow, the listener's tag, TASK; the map's edge between them lights
   from the speaker to the listener, with its arrow;
3. a hand-back is ONE row (TALK, drawn as the hand-back block): the agent finishing adds no OUT beside it; a square
   hand-off says SQUARE and the square's name; no TALK row overflows;
4. the "+" menu adds Conversations: it lists the pairs (newest first), the thread shows each message on its
   speaker's side with its reason, the reply under what it answers; a bubble's click scrolls Live to its row;
   "show in Live" narrows Live to the pair, its chip shows everything again.
Run: python -m tests.test_studio_live_talk
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.test_studio_live_think import _driver, _ran  # noqa: E402

test, TESTS = new_registry()


@test
def test_talk_rows_carry_both_tags_and_the_map_edge_lights(ctx: Ctx):
    r, got = _driver("talk")
    _ran(ctx, r, got)
    ctx.check("Conversations is not open on load", got.get("conv_on_load") is False)
    ctx.check(f"TALK, main, -> researcher, TASK, got {got.get('talk_row')}", got.get("talk_row") == ["TALK", "main", "researcher", "TASK"])
    ctx.check(f"the edge lights from main to the researcher, with its arrow, got {got.get('edge')}", got.get("edge") == [True, True, True])


@test
def test_a_hand_back_is_one_row_and_a_square_names_itself(ctx: Ctx):
    r, got = _driver("talk")
    _ran(ctx, r, got)
    ctx.check(f"the researcher's hand-back: one TALK row drawn as the hand-back block, got {got.get('hand_back')}",
              got.get("hand_back") == [["HAND-BACK", True]])
    ctx.check(f"no OUT row beside it when it finishes, got {got.get('outs_for_res')}", got.get("outs_for_res") == 0)
    ctx.check(f"main's square hand-off, got {got.get('square_why')}", "SQUARE · media" in (got.get("square_why") or []))
    ctx.check(f"no TALK row overflows, got {got.get('overflow')}", got.get("overflow") == [])


@test
def test_conversations_lists_the_pairs_and_the_thread(ctx: Ctx):
    r, got = _driver("talk")
    _ran(ctx, r, got)
    ctx.check(f"the pairs, newest first, got {got.get('pairs')}", got.get("pairs") == ["main ↔ docs", "main ↔ researcher"])
    ctx.check(f"the task left, the reply right and under it, got {got.get('bubbles')}",
              got.get("bubbles") == [["left", "TASK", False], ["right", "HAND-BACK", True]])
    ctx.check("a bubble's click scrolls Live to its row", got.get("away") is True and got.get("bubble_scrolls") is True)
    ctx.check(f"show in Live narrows Live to the pair, got {got.get('pair_chip')!r} {got.get('pair_rows')}",
              str(got.get("pair_chip") or "").startswith("only ") and got.get("pair_rows") == ["talk", "talk"])
    ctx.check("its chip is where a click reaches it", got.get("chip_hit") is True)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
