"""tests.test_studio_compose -- composing blocks on Agents -> Cast (Halo 3.3.16.3 part 2, the owner: "drag and drop those
entire use cases ... add this workflow in there when this situation happens"), in headless Chrome through
tests/helpers/studio_compose.py and studio_compose_drags.py (skipped without one), the real pointer moved through CDP, over a
scratch home on the auto lineup with media, plan and review on its board (review not connected); no model call:

1. nothing opens on load; main's lines go to media and plan with their when labels; review is dashed, says it is not
   connected, and Problems lists it;
2. a line's label opens its When page; pdf only, Save: the label says it and the line says what was written; Undo;
3. main's edge handle dragged onto review asks, then draws its line; Undo takes it off;
4. the library on Cast: three kinds, one search filtering all three;
5. the four drags, each with its confirm card (WHAT / COSTS / WRITES) and its one-line result: a template and a workflow
   onto the canvas (Undo, Redo), a bio into the shipped media (copied to yours first, the card says so), an agent out onto
   the canvas (Undo twice puts the shipped media back), a block by its title bar (saved in the layout; Undo);
6. the keyboard: M, the arrows, Enter raises the card, Esc stops; the block menu by keyboard; no spill, rows >= 40 px.
Run: python -m tests.test_studio_compose
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.driver_got import got as driver_got  # noqa: E402
from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_compose", why="composing blocks needs headless Chrome", cache=_RUN, args=("compose",), timeout=600)


def _card(got: dict, key: str) -> dict:
    return got.get(key) or {}


@test
def test_lines_carry_the_when_and_an_unconnected_block_is_dashed(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"nothing opens on load, got {got.get('load_quiet')} {got.get('load_open')} (open: {got.get('load_seen')})", got.get("load_quiet") is True and got.get("load_open") == [])
    ctx.check(f"main's lines with their labels, got {got.get('load_edges')} {got.get('load_labels')}",
              got.get("load_edges") == ["media", "plan"] and got.get("load_labels") == {"media": "needs pdf, images, audio, video", "plan": "needs a plan"})
    ctx.check(f"review dashed and saying so, got {got.get('load_review')}", got.get("load_review") == [False, "dashed", "not connected: main never uses it"])
    ctx.check(f"Problems lists it, got {got.get('load_problems')}", got.get("load_problems") == ["review"])


@test
def test_the_when_page_and_drawing_a_line(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the When page opens on its covers, got {got.get('when_page')}", got.get("when_page") == ["pdf", "vision", "audio", "video"])
    ctx.check(f"it says what it writes, got {got.get('when_writes')!r}", "workflows.when.media" in str(got.get("when_writes")))
    ctx.check(f"saved: the label and the line, got {got.get('when_saved')!r} {got.get('when_note')!r}",
              got.get("when_saved") == "needs pdf" and "media on the auto lineup: when needs pdf" in str(got.get("when_note")))
    ctx.check(f"Undo puts the covers back, got {got.get('when_undone')!r}", got.get("when_undone") == "needs pdf, images, audio, video")
    card = _card(got, "connect_card")
    ctx.check(f"the handle's drop asks first, got {card}", card.get("title") == "Connect main to review?" and "workflows.when" in card.get("writes", ""))
    ctx.check(f"Connect draws it, got {got.get('connect_drawn')!r} {got.get('connect_note')!r}",
              got.get("connect_drawn") == "needs a review" and "when needs a review" in str(got.get("connect_note")))
    ctx.check(f"Undo takes it off, got {got.get('connect_undone')!r}", got.get("connect_undone") == "off again")


@test
def test_the_library_has_three_kinds_and_one_search(ctx: Ctx):
    got = _got(ctx)
    kinds = dict(got.get("library_kinds") or [])
    ctx.check(f"workflows, blocks, agents, got {kinds}", list(kinds) == ["workflows", "templates", "agents"] and kinds["templates"] == 4 and kinds["agents"] > 3)
    found = dict(got.get("library_search") or [])
    ctx.check(f"the search filters all three, got {found}", found.get("templates", 9) < 4 and found.get("agents", 99) < kinds["agents"] and found.get("workflows", 99) < kinds["workflows"])


@test
def test_a_drop_from_the_library_asks_then_adds_and_undo_takes_it_off(ctx: Ctx):
    got = _got(ctx)
    card = _card(got, "drag_a_card")
    ctx.check(f"the template's card: what, cost, writes, got {card}",
              "thinking" in card.get("title", "") and "auto-planner, auto-reviewer, auto-planner" in card.get("what", "")
              and "band high" in card.get("costs", "") and "~/.halo/workflows/thinking.yaml" in card.get("writes", ""))
    ctx.check(f"the block with three agents, wired, got {got.get('drag_a_block')}", got.get("drag_a_block") == ["auto-planner", "auto-reviewer", "auto-planner"])
    ctx.check(f"its line, got {got.get('drag_a_note')!r}", "thinking added from template thinking" in str(got.get("drag_a_note")))
    ctx.check(f"Undo, Redo, got {got.get('drag_a_undone')!r} {got.get('drag_a_redone')!r}", got.get("drag_a_undone") == "gone" and got.get("drag_a_redone") == "back")
    wf = _card(got, "drag_a_wf_card")
    ctx.check(f"a workflow's card and its block, got {wf} {got.get('drag_a_research')!r}",
              "research" in wf.get("title", "") and "workflows.enabled" in wf.get("writes", "") and got.get("drag_a_research") == "on")


@test
def test_an_agent_into_a_block_and_out_of_it(ctx: Ctx):
    got = _got(ctx)
    card = _card(got, "drag_b_card")
    ctx.check(f"into the shipped media: the card says it is copied first, got {card}",
              card.get("title") == "Add auto-writer to media?" and "copied first" in card.get("writes", ""))
    ctx.check(f"my-media in its place with the writer, got {got.get('drag_b_copy')} {got.get('drag_b_note')!r}",
              got.get("drag_b_copy") == ["auto-media", "auto-writer"] and "copied to yours as my-media first" in str(got.get("drag_b_note")))
    out = _card(got, "drag_c_card")
    ctx.check(f"out onto the canvas asks, got {out}", out.get("title") == "Take auto-writer out of my-media?")
    ctx.check(f"it leaves, Undo puts it back, Undo again the shipped media, got {got.get('drag_c_left')} {got.get('drag_c_back')} {got.get('drag_c_shipped_back')}",
              got.get("drag_c_left") == ["auto-media"] and got.get("drag_c_back") == ["auto-media", "auto-writer"] and got.get("drag_c_shipped_back") == "media")


@test
def test_a_block_moves_by_its_title_bar(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"it moved, got {got.get('drag_d_moved')}", (got.get("drag_d_moved") or 0) > 200)
    ctx.check(f"the layout keeps block:media, got {got.get('drag_d_saved')}", isinstance(got.get("drag_d_saved"), dict))
    ctx.check(f"its line and Undo, got {got.get('drag_d_note')!r} {got.get('drag_d_undone')!r}",
              "media moved" in str(got.get("drag_d_note")) and got.get("drag_d_undone") == "home")


@test
def test_the_keyboard_and_the_density(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"M then the arrows pick a block, got {got.get('keys_hint')!r} -> {got.get('keys_next')!r}",
              bool(got.get("keys_hint")) and got.get("keys_next") != got.get("keys_hint"))
    ctx.check(f"Enter asks, Esc stops, got {_card(got, 'keys_card').get('title')!r} {got.get('keys_stopped')!r}",
              "Add auto-planner to" in _card(got, "keys_card").get("title", "") and got.get("keys_stopped") == "stopped")
    ctx.check(f"the block menu by keyboard, got {got.get('dense_menu')} focus {got.get('dense_menu_focus')!r}",
              got.get("dense_menu") == ["block-menu-when", "block-menu-disconnect", "block-menu-remove"] and got.get("dense_menu_focus") == "block-menu-when")
    ctx.check(f"no spill, got {got.get('dense_spill')} {got.get('dense_menu_spill')} {got.get('dense_page_spill')}",
              got.get("dense_spill") == [] and got.get("dense_menu_spill") == [] and got.get("dense_page_spill") == 0)
    ctx.check(f"the When page's rows >= 40 px, got {got.get('dense_rows')}", bool(got.get("dense_rows")) and min(got.get("dense_rows") or [0]) >= 40)
    ctx.check(f"no step failed, got {got.get('failed')}", not got.get("failed"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
