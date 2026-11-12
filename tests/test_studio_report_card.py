"""tests.test_studio_report_card -- the run report card and Session's mode word in headless Chrome (Halo 3.4.1.0 R3
"Time"), through tests/helpers/studio_report_card.py (skipped without Chrome); no model call:

1. Live with nothing running opens nothing by itself; its row for the session that ended last opens that session's card
   as a page of History (the nine figures, an unpriced cost as "$0.0120+", never $0);
2. every History row but a mission's has a Report door; a session's card shows the story, every section, the files,
   what the record cannot show, Copy; a goal run's Report is its report page with the card as its FIRST block, its
   doors kept;
3. Session's bar says the session's permission mode as one word, its meaning on hover, and follows a change.
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
def test_live_says_the_session_ended_with_a_row_to_its_card(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"nothing opens by itself on load: {got.get('quiet')}", got.get("quiet") is True)
    ctx.check(f"a row for the session that ended last: {got.get('row')} {got.get('row_text')!r}",
              str(got.get("row")).endswith("0002") and "Report card" in str(got.get("row_text")) and "Ship the basket fix" in str(got.get("row_text")))
    b = got.get("b") or {}
    figures = dict(b.get("figures") or [])
    ctx.check(f"its card is a page of History with the nine figures: {got.get('page')} {figures}",
              got.get("page") == "card" and len(figures) == 9 and figures.get("cost") == "$0.0120+" and figures.get("ended") == "finished")
    ctx.check(f"its story: {b.get('story')}", len(b.get("story") or []) == 4 and "main asked reviewer (glm-5.3): review" in str(b.get("story")))


@test
def test_a_rows_report_door_and_a_goal_runs_one_page(ctx: Ctx):
    got = _got(ctx)
    doors = got.get("doors") or []
    ctx.check(f"each row has its own Report door: {doors}", any(d.startswith("session:") for d in doors) and any(d.startswith("run:") for d in doors))
    a = got.get("a") or {}
    ctx.check(f"the story in about ten lines: {a.get('story')}", len(a.get("story") or []) == 9 and "fixer failed" in str(a.get("story")))
    ctx.check(f"every section, in order: {a.get('sections')}", a.get("sections") == SECTIONS)
    ctx.check(f"the files it wrote: {a.get('arts')}", a.get("arts") == ["src/basket.py", "notes-outside.md"])
    ctx.check(f"what the record cannot show, in words: {a.get('cannot')}", any("not in this record" in x for x in a.get("cannot") or []))
    ctx.check("Copy Markdown is on", a.get("copy_on") is True)
    ctx.check(f"a goal run: ONE page, the card its first block: {got.get('run_first')} {got.get('run_ref')}",
              got.get("run_first") == "report-card" and str(got.get("run_ref")).startswith("run:"))
    ctx.check(f"the run's story and its doors kept: {got.get('run_story')}", got.get("run_kept") is True
              and str((got.get("run_story") or [""])[-1]).endswith("The run ended: finished"))


@test
def test_sessions_bar_says_its_permission_mode(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"one small word: {got.get('word')} {got.get('text')!r}", got.get("word") == "auto" and got.get("text") == "auto")
    ctx.check(f"its meaning on hover: {got.get('title')!r}", "every call runs except your own deny and ask rules" in str(got.get("title")))
    ctx.check(f"it follows a change: {got.get('after')!r}", got.get("after") == "plan")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio report card"))
