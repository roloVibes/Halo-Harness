"""tests.test_studio_flows -- Halo 3.6.0.0 R2: Agents -> 2 · Workflows and its builder in headless Chrome, as a first-time
user (driver tests/helpers/studio_flows.py over tests/helpers/crew_rig.py; skipped without Chrome). The room rules over
this tab at 1280 / 1500 / 1920 are tests/test_studio_room.py's (the `flows` view).

1. the 2 key opens 2 · Workflows: the switch reads 1 · Agents | 2 · Workflows | Cast | Live | Board, the list open, the
   five starters, no conversation, no dialog; the empty form says how to start;
2. a starter copied: its steps in the form and drawn; a repeat drawn as a loop mark; a step moved up and back; Save: in
   the list tagged `not on the map`, with the one line that nothing is on a map yet; the file holds the repeat; the
   cost band says what Auto leaves unknown;
3. the steps drawn (R8): fit in their box when the list drawer closes; a zoom by hand survives a drawer; Fit again;
4. the builder: one preview -- the workflow and its steps ticked, the proposed agent's widening lines unticked, the
   card, ghost steps in the form and in the drawing, a ghost row; "make it" fills the agent form, Save comes back with
   its lines out of the preview; Apply writes the workflow; Undo removes it;
5. Write it for me on a saved workflow: the box filled and focused; its step line a ghost step; Discard drops it;
6. Try it: the band first; each step's state and the agents that ran; three checks, the receipt's why; the total;
   marked seen;
7. Delete asks on the page; Keep it; the old board is still there as Board, and the switch comes back.
Run: python -m tests.test_studio_flows
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    slow = {"HALO_STUDIO_SLOW_MS": os.environ["HALO_STUDIO_SLOW_MS"]} if os.environ.get("HALO_STUDIO_SLOW_MS") else None
    return driver_got(ctx, "tests.helpers.studio_flows", why="the Workflows tab is driven in headless Chrome", cache=_RUN, timeout=600,
                      env=slow)  # driver_env drops every HALO_ variable: the latency flag is passed on by name


@test
def test_the_2_key_opens_the_workflows_tab(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"2 lands on 2 · Workflows, got {got.get('view')!r}", got.get("view") == "flows")
    f = got.get("first") or {}
    ctx.check(f"the switch's names, got {f.get('switch')}", f.get("switch") == ["1 · Agents", "2 · Workflows", "Cast", "Live", "Board"])
    ctx.check(f"the list open, no conversation, no dialog, got {f}", f.get("list") is True and f.get("conversation") is False and f.get("dialogs") == 0)
    ctx.check(f"the five starters, got {f.get('starters')}", f.get("starters") == ["code", "media", "plan", "research", "review"])
    ctx.check(f"the empty form says how to start, got {f.get('empty')!r}", f.get("empty") == "Make your first workflow")


@test
def test_copy_steps_repeat_and_save(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a starter's copy with its steps, got {got.get('copied')}",
              got.get("copied") == [["Review", "Test"], "A copy of review, not saved yet: it is yours to change, then Save."])
    ctx.check(f"a repeat is drawn as a loop mark, got {got.get('loop')!r}", got.get("loop") == "↺ until the tests pass, ≤3×")
    ctx.check(f"a step moved up, got {got.get('moved')}", got.get("moved") == ["Test", "Review"])
    ctx.check(f"saved: tagged not on the map, the one line, got {got.get('row')}", got.get("row") == ["not on the map", True])
    ctx.check(f"the file holds the steps and the repeat, got {got.get('file')}", got.get("file") == ["Review", "Test", {"until": "the tests pass", "max": 3}])
    ctx.check(f"the band: Auto leaves it unknown until the first run, got {got.get('cost')!r}",
              got.get("cost") == "unknown until the first run: Auto picks the model (reviewer, tester)")


@test
def test_the_steps_drawn_fit_their_box(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"drawn whole in their box, then whole after the drawer closed, got {got.get('before')} {got.get('closed')}",
              (got.get("before") or [0, False])[1] is True and (got.get("closed") or [0, False])[1] is True)
    hand = got.get("hand") or ["", ""]
    ctx.check(f"a zoom by hand survives the drawer opening, got {hand}", hand[0] and hand[0] == hand[1] and hand[0] != (got.get("closed") or [""])[0])
    ctx.check(f"Fit: automatic again, whole, got {got.get('fit')}", (got.get("fit") or [0, False])[1] is True and (got.get("fit") or [""])[0] != hand[0])


@test
def test_the_builder_one_preview_make_it_apply_undo(ctx: Ctx):
    got = _got(ctx)
    ticks = got.get("ticks") or []
    ctx.check(f"the workflow and its steps ticked, the agent's create ticked, its two widening lines unticked, got {ticks}",
              ticks == [["workflow:review-loop", "0", True]] * 3 + [["agent:my-reviewer", "0", True], ["agent:my-reviewer", "1", False], ["agent:my-reviewer", "1", False]])
    ctx.check(f"the proposal card, got {got.get('card')!r}", got.get("card") == "my-reviewer")
    ctx.check(f"a ghost row and two ghost boxes drawn, got {got.get('ghosts')}", got.get("ghosts") == [["review-loop"], 2])
    ctx.check(f"make it: the agent form filled in, nothing beyond reading switched on, got {got.get('made')}",
              (got.get("made") or [""])[0].startswith("Made for the workflow review-loop, not saved yet") and (got.get("made") or ["", ""])[1] == "false")
    ctx.check(f"Save there: back, the agent's lines out of the preview, got {got.get('unticked')}", got.get("unticked") == [False, False, False])
    ctx.check(f"Apply: the workflow, its agents all there, got {got.get('applied')}", got.get("applied") == [["Review", "Test"], [], ["read"]])
    ctx.check(f"Undo: the workflow is gone, got {got.get('undone')}", got.get("undone") == 404)


@test
def test_write_it_for_me_gives_a_ghost_step(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the box filled and focused, got {got.get('prefill')!r}", got.get("prefill") == "Draft the steps from what it is for")
    ctx.check(f"its step line a ghost step in the form and the drawing, got {got.get('ghost')!r}", got.get("ghost") == "Test")
    ctx.check("Discard: the ghost goes", got.get("gone") is True)


@test
def test_try_it_step_by_step(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the band said first, got {got.get('estimate')!r}", "It costs one run: unknown until the first run" in (got.get("estimate") or ""))
    ctx.check(f"done, each step and its agent, got {got.get('state')} {got.get('steps')}",
              got.get("state") == "done" and got.get("steps") == [["1", "done", ["reviewer"]], ["2", "done", ["tester"]]])
    ctx.check(f"three checks, and why it stopped, got {got.get('checks')} {got.get('why')!r}",
              got.get("checks") == 3 and got.get("why") == '3 rounds: at most 3 times: the check never said yes ("the tests pass")')
    ctx.check(f"the total and where it ran, got {got.get('total')!r}", "$0.0000" in (got.get("total") or "") and "throwaway copy of shop" in (got.get("total") or ""))
    ctx.check(f"drawn in view: seen, got {got.get('seen')}", got.get("seen") == [True])


@test
def test_delete_asks_and_the_board_stays(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the question, got {got.get('ask')!r}", got.get("ask") == "Delete my-review? Its file goes; nothing else changes.")
    ctx.check(f"Keep it: still there, got {got.get('kept')}", got.get("kept") == [True, 200])
    ctx.check(f"the old board as Board, then back, got {got.get('board')!r} {got.get('back')!r}", got.get("board") == "board" and got.get("back") == "my-review")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
