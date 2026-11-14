"""tests.test_studio_model_pickers_ui -- Halo 3.4.1.3 "Pick, don't type" in headless Chrome (tests/helpers/
studio_model_pickers.py; skipped without one), over a fresh home with two fake OpenRouter models, no model call:

1. Agents -> Models: "Test a model" is the picker field (a button, not a text box); the panel scrolls sideways
   neither closed nor open; a click focuses the picker's search, the rows are grouped by provider with its state,
   typing filters to one row (highlighted), Enter picks it and closes, Test answers beside the field;
2. a letter on the closed field opens the picker with that letter searched; Esc closes it;
3. the last row: a wrong prefix names the known ones and Use it stays off; a good ref is checked as typed, Enter uses
   it, the field marks it "not in your catalog" and the picker shows it as its saved row;
4. Settings: compactionModel's picker saves a row and its first row resets the key; every role's model is the
   picker; embeddings.model lists Ollama models only and says why it is empty.
Run: python -m tests.test_studio_model_pickers_ui
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
ALPHA, BETA = "or:fakeco/alpha-1", "or:fakeco/beta-2"


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_model_pickers", why="the model picker checks need headless Chrome", cache=_RUN,
                      args=("pickers",), timeout=400, tail=600, stdin=False)


@test
def test_test_a_model_is_a_picker_that_fits_its_panel(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the field is a button, got {got.get('is_button')!r}", got.get("is_button") == "BUTTON")
    ctx.check(f"nothing scrolls sideways, closed or open, got {got.get('sideways_closed')} {got.get('sideways_open')}",
              got.get("sideways_closed") == [] and got.get("sideways_open") == [])
    ctx.check(f"a click focuses the search, got {got.get('search_focused')!r}", got.get("search_focused") == "focused")
    ctx.check(f"the catalog's rows, grouped by provider with its state, got {got.get('rows')} {got.get('groups')}",
              got.get("rows") == [ALPHA, BETA] and len(got.get("groups") or []) == 1 and "2 models" in str(got.get("groups")))


@test
def test_type_to_filter_enter_picks_esc_closes(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"typing filters to one highlighted row, got {got.get('typed_rows')}", got.get("typed_rows") == [[BETA, True]])
    ctx.check(f"Enter picks it and closes, got {got.get('enter_pick')!r}", got.get("enter_pick") == BETA)
    ctx.check(f"Test answers beside it, got {got.get('probe')!r}", got.get("probe") == "fakeco/beta-2: ok in 42 ms")
    ctx.check(f"a letter opens it searched, got {got.get('key_open')!r}", got.get("key_open") == "a")
    ctx.check("Esc closes it", got.get("esc_closed") == "closed")
    ctx.check("an Esc before the search box has the focus closes it too", got.get("esc_on_field_closed") == "closed")


@test
def test_the_last_row_checks_a_ref_the_catalog_lacks(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"a wrong prefix names the known ones, got {got.get('bad_line')!r}",
              "zz:" in str(got.get("bad_line")) and "or:" in str(got.get("bad_line")) and got.get("bad_use_off") is True)
    ctx.check(f"a good ref is checked as typed, got {got.get('good_line')!r}", "OpenRouter" in str(got.get("good_line")))
    ctx.check(f"Enter uses it, got {got.get('typed_value')!r}", got.get("typed_value") == "or:vendor/other-9")
    ctx.check(f"the field marks it, got {got.get('off_mark')!r}", got.get("off_mark") == "not in your catalog")
    ref, text = (got.get("saved_row") or [None, ""])
    ctx.check(f"the picker keeps it as its saved row, got {got.get('saved_row')}", ref == "or:vendor/other-9" and "not in your catalog" in str(text))


@test
def test_settings_model_rows_are_the_picker(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"compactionModel lists the catalog, got {got.get('settings_rows')}", got.get("settings_rows") == [ALPHA, BETA])
    ctx.check(f"a row saves the key, got {got.get('compaction_saved')!r}", got.get("compaction_saved") == BETA)
    ctx.check("the first row (the default) resets it", got.get("compaction_reset") is True)
    ctx.check(f"every role's model is the picker, got {got.get('role_fields')}", (got.get("role_fields") or 0) >= 5)
    ctx.check(f"embeddings.model lists Ollama models only and says so, got {got.get('embed_why')!r}",
              "no Ollama model is listed here" in str(got.get("embed_why")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
