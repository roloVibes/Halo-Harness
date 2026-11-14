"""tests.test_studio_crew -- Halo 3.6.0.0 R1: Agents -> 1 · Agents and its builder in headless Chrome, as a first-time
user (driver tests/helpers/studio_crew.py over tests/helpers/crew_rig.py; skipped without Chrome). The room rules over
this tab at 1280 / 1500 / 1920 are tests/test_studio_room.py's (the `crew` view).

1. Alt+2 from Session opens Agents on 1 · Agents: the list open beside the form, the builder's line, no conversation,
   no dialog; the empty form says how to start; the ten starters;
2. a starter copied is in the form, not saved; Save puts it in the list tagged `new` and `not used yet`;
3. a switch and a careful mode, Save: the file has them;
4. the builder's preview: the agent ticked, every widening line unticked, a ghost row; Apply writes the agent as the
   ticked lines say; Undo removes it;
5. Write it for me fills the box (focused); its preview line, Apply: the form holds the draft;
6. Try it: the cost line before; the result in the tab (the mock's reply, Glob used, where it ran); marked seen;
7. Delete asks on the page; Keep it keeps it.
Run: python -m tests.test_studio_crew
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
STARTERS = ["coder", "implementer", "main", "media-reader", "ops", "planner", "researcher", "reviewer", "tester", "writer"]


def _got(ctx: Ctx) -> dict:
    slow = {"HALO_STUDIO_SLOW_MS": os.environ["HALO_STUDIO_SLOW_MS"]} if os.environ.get("HALO_STUDIO_SLOW_MS") else None
    return driver_got(ctx, "tests.helpers.studio_crew", why="the Agents tab is driven in headless Chrome", cache=_RUN, timeout=420,
                      env=slow)  # driver_env drops every HALO_ variable: the latency flag is passed on by name


@test
def test_alt2_opens_the_agents_tab_quietly(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Alt+2 lands on 1 · Agents, got {got.get('view')!r}", got.get("view") == "crew")
    f = got.get("first") or {}
    ctx.check(f"the list open, no conversation, no dialog, the switch pressed, got {f}",
              f.get("list") is True and f.get("conversation") is False and f.get("dialogs") == 0 and f.get("pressed") == "true")
    ctx.check(f"the empty form says how to start, got {f.get('empty')!r}", f.get("empty") == "Make your first agent")
    ctx.check(f"the ten starters to copy, got {f.get('starters')}", f.get("starters") == STARTERS)
    ctx.check(f"the builder's line: model, a request's cost, today's spend of the cap, got {f.get('meta')!r}",
              "about $0.01-0.03 a request" in (f.get("meta") or "") and "of $1.00 today" in (f.get("meta") or ""))


@test
def test_copy_save_and_edit(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a starter's copy, not saved, Save ready, got {got.get('copied')}",
              got.get("copied") == ["my-reviewer", "A copy of reviewer, not saved yet: it is yours to change, then Save.", False])
    ctx.check(f"saved: in the list, new and not used yet, got {got.get('saved_row')}", got.get("saved_row") == ["new", "unused"])
    ctx.check(f"a switch and a careful mode saved, got {got.get('edited')}", got.get("edited") == [["read", "bash"], "ask-commands"])
    st = got.get("edit_states") or [[], []]
    ctx.check(f"the form said Not saved yet, then Saved with Save resting, the switch on throughout, got {st}",
              st == [["Not saved yet.", False, "true"], ["Saved my-reviewer.", True, "true"]])


@test
def test_the_builder_preview_apply_undo(ctx: Ctx):
    got = _got(ctx)
    ticks = got.get("ticks") or []
    ctx.check(f"the agent ticked, four widening lines, none ticked, got {ticks}", ticks == [["0", True]] + [["1", False]] * 4)
    ctx.check(f"a ghost row in the list, got {got.get('ghost')}", got.get("ghost") == ["security-gate"])
    ctx.check(f"Apply: the agent reads only and asks before changes, got {got.get('applied')}", got.get("applied") == [["read"], "ask-changes"])
    ctx.check(f"Undo: it is gone, got {got.get('undone')}", got.get("undone") == 404)


@test
def test_write_it_for_me(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the box filled and focused, got {got.get('prefill')!r}", got.get("prefill") == "Write the instructions for my-reviewer from what it does")
    ctx.check(f"one change line, got {got.get('lines')}", got.get("lines") == ["change"])
    ctx.check("Apply: the form holds the draft", got.get("instructions") == "draft")


@test
def test_try_it_in_the_tab(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the cost said before the run, got {got.get('estimate')!r}", "Cost: Auto picks the model when it runs" in (got.get("estimate") or ""))
    used = (got.get("result") or ["", ""])[1] or ""
    ctx.check(f"the reply in the tab, got {got.get('result')}", got.get("reply_ok") is True)
    ctx.check(f"the tools, the cost, where it ran, got {used!r}", used.startswith("Used: Glob") and "$0.0000" in used and "throwaway copy of shop" in used)
    ctx.check(f"drawn in view: seen, got {got.get('seen')}", got.get("seen") == [True])


@test
def test_delete_asks_on_the_page(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the question, got {got.get('ask')!r}", got.get("ask") == "Delete my-reviewer? Its file goes; nothing else changes.")
    ctx.check(f"Keep it: still there, got {got.get('still')}", got.get("kept") is True and got.get("still") == 200)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
