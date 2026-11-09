"""tests.test_studio_models_ui -- what each model is good at, in Studio (Halo
3.1.9.0 R1). Headless Chrome through the driver base (tests/helpers/
studio_ui_models.py; skipped without one), over a fresh home with the shipped
lineups and a fixture catalog in every provider's cache:

1. the Models panel's Analyze shows the models analyzed, the count per kind
   and each kind's strongest model;
2. the bio form's picker table has a "takes" column (3.3.15.0 R2): a row's
   takes as tags, the focused row's honest line and ranked kinds on the
   detail line under the list, the full line on the tags' hover;
3. the "best" sort leads with the model good at the most kinds; a search by
   the line's words finds the rows that say it.
Run: python -m tests.test_studio_models_ui
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
_RUN: dict = {}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_ui_models", why="the Studio models checks need headless Chrome",
                      cache=_RUN, timeout=400, tail=500, stdin=False)
    return info


@test
def test_analyze_shows_the_counts_per_kind(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the panel counts the catalog, got {got.get('count')}", isinstance(got.get("count"), (int, float)) and got["count"] >= 10)
    ctx.check(f"Analyze says how many and per kind, got {got.get('analysis')!r}",
              "models analyzed" in str(got.get("analysis")) and "visual" in str(got.get("analysis")))
    ctx.check(f"each kind's strongest model is named, got {got.get('analysis_kinds')}",
              {"visual", "audio", "bulk"} <= set(got.get("analysis_kinds") or []))


@test
def test_the_picker_has_a_takes_column_and_a_detail_line(ctx: Ctx):
    """3.3.15.0 R2 (owner feedback 2026-11-09, "the chips"): the best-at column became TAKES (tags only); the honest
    line and the ranked kinds moved to the detail line under the list."""
    got = _got(ctx)
    ctx.check(f"the table lists the catalog, got {got.get('rows')}", (got.get("rows") or 0) >= 10)
    ctx.check(f"the column header says takes, got {got.get('head')!r}", "takes" in str(got.get("head")) and "best at" not in str(got.get("head")))
    ctx.check(f"a row's takes are tags, got {got.get('eyes_kinds')}", got.get("eyes_kinds") == ["vision", "pdf", "tools", "think"])
    ctx.check(f"the focused row's line is the detail line, got {got.get('eyes_line')!r}",
              got.get("eyes_line") == "vision+pdf in, tools, reasoning; no audio" and got.get("eyes_row_line") is False)
    ctx.check(f"the ranked kinds sit on that line, got {got.get('eyes_best')!r}", "visual" in str(got.get("eyes_best")))
    ctx.check("the full line is on the tags' hover", got.get("eyes_title") == got.get("eyes_line"))
    ctx.check("no dialog opened on the way", got.get("dialogs") == 0)


@test
def test_best_sort_and_the_line_search(ctx: Ctx):
    got = _got(ctx)
    first = got.get("best_first") or []
    ctx.check(f"the best sort leads with the most kinds, got {first} (max {got.get('max_chips')})",
              bool(first) and first[0][1] == got.get("max_chips"))
    refs = got.get("pdf_search") or []
    ctx.check(f"a search by the line's words finds the rows that say it, got {refs}", "or:v/eyes" in refs and "or:v/cheap" not in refs)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
