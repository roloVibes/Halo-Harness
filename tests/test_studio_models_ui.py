"""tests.test_studio_models_ui -- what each model is good at, in Studio (Halo
3.1.9.0 R1). Headless Chrome through the driver base (tests/helpers/
studio_ui_models.py; skipped without one), over a fresh home with the shipped
lineups and a fixture catalog in every provider's cache:

1. (3.6.0.0 R5: the Models panel's Analyze went with Roles' panels;)
2. an agent's MODEL picker (Agents -> 1 · Agents; the bio form's before) has a "takes" column (3.3.15.0 R2): a row's
   takes as tags, the focused row's honest line and ranked kinds on the
   detail line under the list, the full line on the tags' hover;
3. the "best" sort leads with the model good at the most kinds; a search by
   the line's words finds the rows that say it;
4. the picker's bar holds still while the rows under it change (3.6.0.0 R5c);
5. the keyboard walks every row while the pointer rests over the list, and a row focused, Best pressed or a filter
   typed while the picker's answers are on their way survives them (3.6.0.0 R5e).
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
    ctx.check(f"the picker is the one dialog (the form's MODEL opens it; 3.6.0.0 R5), got {got.get('dialogs')}",
              got.get("dialogs") == ["model-select-dialog"])


@test
def test_best_sort_and_the_line_search(ctx: Ctx):
    got = _got(ctx)
    first = got.get("best_first") or []
    ctx.check(f"the best sort leads with the most kinds, got {first} (max {got.get('max_chips')})",
              bool(first) and first[0][1] == got.get("max_chips"))
    refs = got.get("pdf_search") or []
    ctx.check(f"a search by the line's words finds the rows that say it, got {refs}", "or:v/eyes" in refs and "or:v/cheap" not in refs)


@test
def test_the_pickers_bar_holds_still_while_you_use_it(ctx: Ctx):
    """3.6.0.0 R5c: pointing at a row with another detail line or filtering to fewer rows moves nothing in the bar (the
    picker's dialog sits at the top; the detail line is one line). Centred, Best moved under a click (Windows CI)."""
    got = _got(ctx)
    ctx.check(f"the search and the sorts stay put, got {got.get('bar_moves')}", got.get("bar_moves") == [])


@test
def test_the_keyboard_walks_the_rows_under_a_resting_pointer(ctx: Ctx):
    """3.6.0.0 R5e (Windows CI, three times): with the pointer resting over the list, each Down scrolled the list under
    it and Chrome reported the row now under the pointer as entered (no move); that row took the highlight, the detail
    line showed it and Down started again from it. Only a pointer that moves takes the highlight now."""
    got = _got(ctx)
    walked = got.get("rest_walked") or []
    ctx.check(f"Down reaches the last row, got {walked}", bool(walked) and walked[-1] == got.get("rest_last"))
    ctx.check(f"the detail line follows the keyboard, got {got.get('rest_detail')!r}", got.get("rest_detail") == got.get("rest_last"))


@test
def test_a_choice_made_early_in_the_picker_survives(ctx: Ctx):
    """3.6.0.0 R5e: a row focused, Best pressed or a filter typed while the catalog, the providers' state, the best-at
    kinds and the gym are still on their way (tests/helpers/hold_still.survives) still stands once they have all landed,
    oldest first and newest first: the focused row's detail line, Best pressed, the filter applied."""
    got = _got(ctx)
    for name in ("focus", "best", "filter"):
        for order in ("oldest", "newest"):
            v = got.get(f"early_{name}/{order}") or {}
            ctx.check(f"{name} ({order} first): made, got {v}", v.get("made") is True and not v.get("error"))
            ctx.check(f"{name} ({order} first): still in effect at the end, lost after {v.get('lost')!r} ({v.get('released')})", v.get("lost") == "")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
