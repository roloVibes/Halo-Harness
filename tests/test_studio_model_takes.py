"""tests.test_studio_model_takes -- what a model takes, wherever a model is
picked in Studio (Halo 3.3.15.0 R2, "the picker says what a model takes").
Headless Chrome through the driver base (tests/helpers/studio_model_takes.py;
skipped without one), over a fake OpenRouter catalog of a vision+pdf model
with tools and reasoning and a text-only one:

1. the Session section's new-session select shows the default model's
   `model-takes` chips (the same words as the terminal's takes= column), each
   chip's title the honest line; a pick turns them to the picked model's;
2. Orchestra's goal form: the model select shows the lead's chips, and a pick
   turns them to the picked model's; the select's title carries the takes too;
3. its "more..." table (Roles' picker): every row one line (<= 28 px), no tag
   taller than 20 px, TAKES holds the tags only, the honest line is the detail
   line under the list (owner feedback 2026-11-09, "the chips").
Run: python -m tests.test_studio_model_takes
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
_RUN: dict = {}
EYES_TAKES = "text,vision,pdf,tools,think"


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_model_takes", why="the model takes checks need headless Chrome",
                      cache=_RUN, timeout=300, tail=400, stdin=False)


@test
def test_the_new_session_select_shows_what_the_model_takes(ctx: Ctx):
    got = _got(ctx)
    default = got.get("session_default") or ["", ""]
    ctx.check(f"the default model's chips, the honest line as their title, got {default}",
              default[0] == EYES_TAKES and str(default[1]).startswith("vision+pdf in, tools, reasoning"))
    ctx.check(f"an option's title says it too, got {got.get('session_option_title')!r}",
              f"takes {EYES_TAKES}" in str(got.get("session_option_title")))
    picked = got.get("session_picked") or ["", ""]
    ctx.check(f"a pick turns them to the text-only model's, got {picked}", picked[0] == "text" and "text in only" in str(picked[1]))


@test
def test_orchestras_goal_form_shows_what_the_model_takes(ctx: Ctx):
    got = _got(ctx)
    lead = got.get("orch_lead") or ["", ""]
    ctx.check(f"the lead's (text-only) chips, got {lead}", lead[0] == "text")
    picked = got.get("orch_picked") or ["", ""]
    ctx.check(f"a pick turns them to the picked model's, got {picked} / {got.get('orch_value')!r}",
              picked[0] == EYES_TAKES and got.get("orch_value") == "or:fakeco/eyes-1" and "vision+pdf" in str(picked[1]))
    ctx.check(f"the select's title carries the takes, got {got.get('orch_select_title')!r}",
              f"takes {EYES_TAKES}" in str(got.get("orch_select_title")))


@test
def test_the_picker_table_rows_are_one_line_with_square_tags(ctx: Ctx):
    """Owner feedback 2026-11-09 ("the chips"): one row = one line, fixed-height tags in a fixed order, the TAKES
    column holds the tags only, the honest line is the detail line under the list."""
    got = _got(ctx)
    heights, tags = got.get("row_heights") or [], got.get("tag_heights") or []
    ctx.check(f"every row is one line (<= 28 px), got {heights}", len(heights) == 2 and all(0 < h <= 28 for h in heights))
    ctx.check(f"no tag taller than 20 px, got {tags}", tags and all(0 < h <= 20 for h in tags))
    ctx.check(f"the tags in their order, text-only reads 'text in', got {got.get('row_tags')}",
              sorted(got.get("row_tags") or []) == [["or:fakeco/eyes-1", "vision pdf tools think"], ["or:fakeco/plain-2", "text in"]])
    ctx.check(f"the header says takes, not best at, got {got.get('head')!r}",
              "takes" in str(got.get("head")) and "best at" not in str(got.get("head")))
    ctx.check("no honest line inside a row", got.get("no_line_in_rows") is True)
    ctx.check(f"the focused row's line is the detail line, got {got.get('detail')!r}", "text in only" in str(got.get("detail")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped, label="studio model takes"))
