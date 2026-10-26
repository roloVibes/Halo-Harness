"""tests.test_studio_roles_tiers -- tiers on the Roles canvas, in a real browser
(Halo 3.1.6.0 R1; the owner: "how do I create custom tiers to then put models
and agents in new tiers? I may want a media tier or if something else trigger
that whole tier of agents ... That should be much easier to add in the
canvas"). Headless Chrome through the driver base (tests/helpers/
studio_roles_tiers.py and studio_roles_tier_menu.py; skipped without one),
over a one-tier lineup (halo-dev-cycle, no tiers declared):

1. the fan's edge labels never overlap (main selected, and nothing selected);
2. Add tier on the bar: tier 0 = main alone, the new box empty with "Drag
   cards here" in its holo brackets, the boxes laid out so none overlaps;
3. a card dragged in, a double-click rename, a reload: the file on disk and
   the canvas agree;
4. the palette's "Roles: add tier" opens the bar's field; the box menu:
   Rename, Model (the tier's model on disk, its pill, the card under it
   showing it and saying it comes from the tier), Trigger (a schedule every
   30m with its prompt, the chip), Max parallel;
5. a second tier with a card in it: the labels on the three-tier lineup never
   overlap; Delete (tier 0's is off) puts its card back in the last tier;
   Ctrl+Z brings it back.

3.2.2.0 R5, the canvas makes room (tests/helpers/studio_roles_room.py, over
studio-tiers): a card dropped onto another in its tier leaves both visible
and not overlapping, the dropped one on top; dropped onto a card in another
tier it moves there and lands beside it; dropped on a collapsed tier's strip
it is not hidden and stays where it was (the toast says so), held there the
tier opens and the drop joins it; a card removed and saved keeps every other
card's id and its spot in the layout file.
Run: python -m tests.test_studio_roles_tiers
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, SkipTest, new_registry, print_results, run_all  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx, helper: str = "tests.helpers.studio_roles_tiers", mode: str = "tiers") -> dict:
    from tests.helpers.chrome_driver import driver_env, find_chrome
    if not find_chrome():
        raise SkipTest("no Chrome found (the Roles tier checks need headless Chrome)")
    if helper not in _RUN:
        r = subprocess.run([sys.executable, "-m", helper, mode], capture_output=True, encoding="utf-8",
                           errors="replace", timeout=500, env=driver_env(REPO), cwd=str(REPO))
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            info = {}
        _RUN[helper] = (r, info)
    r, info = _RUN[helper]
    if info.get("skip"):
        raise SkipTest(info["skip"])
    ctx.check(f"the driver ran, got {r.returncode} {info.get('failed')!r} {r.stderr[-600:]!r}", r.returncode == 0 and "failed" not in info)
    return info


def _clear(ctx: Ctx, key: str, got: dict, least: int) -> None:
    lb = got.get(key) or {}
    ctx.check(f"{key}: at least {least} labels shown and no two overlap, got {lb}", lb.get("shown", 0) >= least and lb.get("overlaps") == 0)


@test
def test_the_fan_labels_never_overlap(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"one tier box, seven cards, got {got.get('fan_tiers')} {got.get('cards')}", got.get("fan_tiers") == 1 and got.get("cards") == 7)
    _clear(ctx, "fan_selected", got, 6)
    _clear(ctx, "fan_plain", got, 1)


@test
def test_add_tier_declares_tier_zero_and_an_empty_box(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"tier 0 = main alone, the new tier empty, got {got.get('added')}", got.get("added") == {"top": ["boss"], "media": []})
    ctx.check(f"'Drag cards here' in the holo brackets, got {got.get('drop_hint')!r} {got.get('drop_brackets')}",
              got.get("drop_hint") == "Drag cards here" and got.get("drop_brackets") is True)
    ctx.check("the name field closes, and no two tier boxes overlap", got.get("bar_closed") is True and got.get("boxes_overlap_after_add") is False)


@test
def test_drag_in_rename_and_reload(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the card dragged in lands in the file, got {got.get('dragged')}", got.get("dragged") == {"top": ["boss"], "media": ["worker"]})
    ctx.check("and sits in the box", got.get("in_box") is True)
    ctx.check(f"a double-click rename, got {got.get('renamed')}", got.get("renamed") == {"top": ["boss"], "studio-media": ["worker"]})
    ctx.check(f"after a reload the box and its card are back, got {got.get('reloaded')} {got.get('after_reload')}",
              got.get("reloaded") == "in" and got.get("after_reload") == {"top": ["boss"], "studio-media": ["worker"]})


@test
def test_the_palette_opens_add_tier_and_the_menu_renames(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"'Roles: add tier' opens the bar's name field, Escape closes it, got {got.get('palette_field')!r} {got.get('palette_field_closed')!r}",
              got.get("palette_field") == "open" and got.get("palette_field_closed") == "closed")
    ctx.check(f"the menu's Rename opens the head's field on the name, Escape keeps it, got {got.get('menu_rename')!r} {got.get('menu_rename_kept')!r}",
              got.get("menu_rename") == "studio-media" and got.get("menu_rename_kept") == "kept")


@test
def test_the_menu_sets_the_tier_model(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the menu's items, got {got.get('menu_items')}", got.get("menu_items") == ["rename", "model", "trigger", "max", "delete"])
    ctx.check(f"its first option is the session's model, got {got.get('model_first_option')!r}",
              str(got.get("model_first_option")).startswith("the session's") and "deepseek-chat" in str(got.get("model_first_option")))
    ctx.check(f"saved, the pill shows it, the menu closes, got {got.get('model_on_disk')} {got.get('model_pill')!r} {got.get('menu_closed')}",
              got.get("model_on_disk") == "or:qwen/qwen3-coder" and "qwen3-coder" in str(got.get("model_pill")) and got.get("menu_closed") == "closed")
    pill = got.get("card_pill") or ["", "", ""]
    ctx.check(f"the card under it runs on it and says it comes from the tier, got {pill}",
              "qwen3-coder" in pill[0] and "from tier studio-media's model" in pill[1] and pill[2] == "tier:studio-media")


@test
def test_the_menu_sets_the_trigger_and_max_parallel(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the trigger on disk, got {got.get('trigger_on_disk')}",
              got.get("trigger_on_disk") == {"on": "schedule", "every": "30m", "prompt": "Cut the new clips"})
    ctx.check(f"its chip, got {got.get('trigger_chip')!r}", got.get("trigger_chip") == "⚡ every 30m")
    ctx.check(f"max parallel 2 on disk and on the head, got {got.get('max_on_disk')} {got.get('max_count')!r}",
              got.get("max_on_disk") == 2 and "max 2" in str(got.get("max_count")))


@test
def test_three_tiers_labels_delete_and_undo(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a second tier with the reviewer in it, got {got.get('three_tiers')}",
              got.get("three_tiers") == {"top": ["boss"], "studio-media": ["worker"], "review-tier": ["review"]})
    _clear(ctx, "three_selected", got, 6)
    _clear(ctx, "three_plain", got, 1)
    ctx.check("tier 0 cannot be deleted", got.get("top_delete_disabled") is True)
    ctx.check(f"Delete drops the tier, its card back in the last tier, got {got.get('deleted')} {got.get('review_in_rest')!r}",
              got.get("deleted") == {"top": ["boss"], "studio-media": ["worker"]} and got.get("review_in_rest") == "rest")
    ctx.check(f"Ctrl+Z brings it back (unsaved), got {got.get('undo_back')!r}", got.get("undo_back") == "back")


def _room(ctx: Ctx) -> dict:
    return _got(ctx, "tests.helpers.studio_roles_room", "room")


@test
def test_a_drop_onto_a_card_in_its_tier_makes_room(ctx: Ctx):
    got = _room(ctx)
    ctx.check(f"no two cards overlap before, got {got.get('start_overlaps')}", got.get("start_overlaps") == [])
    ctx.check("both cards stay drawn", got.get("same_both_shown") is True)
    ctx.check(f"and no two overlap, got {got.get('same_overlaps')}", got.get("same_overlaps") == [])
    ctx.check(f"the dropped card is on top (z-index 2), got {got.get('same_top')!r}", str(got.get("same_top")) == "2")


@test
def test_a_drop_onto_a_card_in_another_tier_lands_beside_it(ctx: Ctx):
    got = _room(ctx)
    ctx.check(f"the tier move is saved, got {got.get('moved_tiers')}", (got.get("moved_tiers") or {}).get("leads") == ["worker", "research", "release"])
    ctx.check("both cards stay drawn, the moved one inside its new box", got.get("other_both_shown") is True and got.get("other_in_leads") == "in")
    ctx.check(f"beside it, not on it: no two cards overlap, got {got.get('other_overlaps')}", got.get("other_overlaps") == [])


@test
def test_a_collapsed_tier_is_no_drop_target(ctx: Ctx):
    got = _room(ctx)
    ctx.check("the strip collapsed", got.get("leads_collapsed") == "collapsed")
    ctx.check(f"a quick drop on it: the toast, got {got.get('shut_toast')!r}", got.get("shut_toast") == "tier leads is collapsed; it stays where it was")
    ctx.check("the card is still drawn, the tiers on disk unchanged, the tier still collapsed",
              got.get("shut_shown") is True and got.get("shut_unchanged") is True and got.get("shut_still_collapsed") is True)
    ctx.check("held over the strip, the tier opens", got.get("held_opened") is True)
    ctx.check(f"and the drop joins it, drawn, nothing overlapping, got {got.get('held_joined')} {got.get('held_overlaps')}",
              "watchdog" in (got.get("held_joined") or {}).get("leads", []) and got.get("held_shown") is True and got.get("held_overlaps") == [])
    ctx.check(f"the joined card sits inside the leads tier box (3.3.0.0 R1), got card / box {got.get('held_rects')}",
              got.get("held_in_box") is True)


@test
def test_removing_a_card_keeps_the_others_spots(ctx: Ctx):
    got = _room(ctx)
    ctx.check(f"the removed card is scout#0, the lineup saved without it, got {got.get('removed_id')!r} {got.get('saved_agents')}",
              got.get("removed_id") == "scout#0" and "tester" not in (got.get("saved_agents") or ["tester"]))
    ctx.check(f"seven other cards in the layout before, got {got.get('others')}", len(got.get("others") or []) == 7)
    # 3.3.0.0 R1: judged on every runner again (the Windows runner's three moved cards came from the held drop landing
    # outside the leads box, fixed in routes/roles/drop.ts)
    ctx.check(f"every one keeps its id and its spot in the layout file, got {got.get('kept')} of {got.get('others')}",
              got.get("kept") == got.get("others") and got.get("removed_id") not in (got.get("layout_after") or {"scout#0": 1}))
    ctx.check(f"and nothing overlaps, got {got.get('after_overlaps')}", got.get("after_overlaps") == [])


if __name__ == "__main__":
    results, passed, failed, skipped = run_all(TESTS, Ctx())
    sys.exit(print_results(results, passed, failed, skipped))
