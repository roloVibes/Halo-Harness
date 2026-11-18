"""tests.test_studio_report_card -- the run report card and Session's mode word in headless Chrome (Halo 3.4.1.0 R3
"Time"), through tests/helpers/studio_report_card.py (skipped without Chrome); no model call:

1. (3.6.0.3 B: History and a past session's card left Studio) a goal run's card on its own page (`&run=<id>`): the
   nine figures, the story, every section, its file, what the record cannot show, Copy; the card is the report page's
   FIRST block, the report's doors kept;
2. Session's bar says the session's permission mode as one word, its meaning on hover, and follows a change;
3. (3.6.0.3 B) a finished goal run's report is its own drawer page `report:<id>`, "Goal run", from `&run=<id>` and the
   palette; the view bar's drawer button holds still between it and Run a goal.
Run: python -m tests.test_studio_report_card
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
SECTIONS = ["story", "time", "money", "failures", "waits", "models", "artefacts", "cannot"]


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_report_card", why="the report card needs headless Chrome", cache=_RUN, timeout=300)


@test
def test_a_goal_runs_card_on_its_own_page(ctx: Ctx):
    got = _got(ctx)
    a = got.get("a") or {}
    ctx.check(f"the nine figures: {a.get('figures')}", len(a.get("figures") or []) == 9)
    ctx.check(f"every section, in order: {a.get('sections')}", a.get("sections") == SECTIONS)
    ctx.check(f"the file it wrote: {a.get('arts')}", a.get("arts") == ["basket.py"])
    ctx.check(f"what the record cannot show, in words: {a.get('cannot')}", any("not in this record" in x for x in a.get("cannot") or []))
    ctx.check("Copy Markdown is on", a.get("copy_on") is True)
    ctx.check(f"a goal run: ONE page, the card its first block: {got.get('run_first')} {got.get('run_ref')}",
              got.get("run_first") == "report-card" and str(got.get("run_ref")).startswith("run:"))
    ctx.check(f"the run's story and its doors kept: {got.get('run_story')}", got.get("run_kept") is True
              and str((got.get("run_story") or [""])[-1]).endswith("The run ended: finished"))


@test
def test_a_finished_goal_runs_report_is_its_own_page_from_its_doors(ctx: Ctx):
    """3.6.0.3 B batch 1: `&run=<id>` and the palette's "Goal run <id>" open the drawer page `report:<id>`, titled
    "Goal run", History's list not open; the report the same as before (the card first, its doors kept); Back with no run
    page behind it closes the drawer; the view bar's drawer button has one rect on the report and goal pages."""
    got = _got(ctx)
    ctx.check(f"the step ran whole: {got.get('failed')}", not got.get("failed"))
    run = str(got.get("run_ref") or "").split(":", 1)[-1]
    for door in ("url", "palette"):
        d = got.get(door) or {}
        ctx.check(f"{door}: the drawer page is report:<id>, got {d.get('page')!r}", bool(run) and d.get("page") == f"report:{run}")
        ctx.check(f"{door}: the drawer's title is 'Goal run', got {d.get('title')!r}", d.get("title") == "Goal run")
        ctx.check(f"{door}: History's list is not open, got {d.get('history_open')!r}", d.get("history_open") is False)
        ctx.check(f"{door}: the card first, the doors kept, got {d.get('first')!r} {d.get('kept')!r}",
                  d.get("first") == "report-card" and d.get("kept") is True)
        ctx.check(f"{door}: Back names no History, got {d.get('back_title')!r}", "history" not in str(d.get("back_title")).lower())
    ctx.check(f"the palette's line reads 'Goal run <id>', got {got.get('palette_first')!r}", got.get("palette_first") == f"Goal run {run}")
    ctx.check(f"Back with no run page behind it closes the drawer, got {got.get('back_shut')!r}", got.get("back_shut") == "shut")
    goal = got.get("goal") or {}
    ctx.check(f"the goal form's page keeps its title, got {goal.get('title')!r}", goal.get("title") == "Run a goal")
    rects = [(got.get("url") or {}).get("rect"), (got.get("palette") or {}).get("rect"), goal.get("rect")]
    ctx.check(f"the view bar's drawer button holds still on every drawer page, got {rects}", rects[0] is not None and all(r == rects[0] for r in rects))


@test
def test_sessions_bar_says_its_permission_mode(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"one small word: {got.get('word')} {got.get('text')!r}", got.get("word") == "auto" and got.get("text") == "auto")
    ctx.check(f"its meaning on hover: {got.get('title')!r}", "every call runs except your own deny and ask rules" in str(got.get("title")))
    ctx.check(f"it follows a change: {got.get('after')!r}", got.get("after") == "plan")
    ctx.check(f"3.4.1.0 R6: the mode moved before any frame of the session reached Studio: the page's first word is the "
              f"registry's, got {got.get('first_after')!r}", got.get("first_after") == "plan")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio report card"))
