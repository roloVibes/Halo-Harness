"""tests.test_studio_roles_model -- the model is where you look, in Roles
(Halo 3.1.4.0 R4; the owner: "I can't figure out where the model drop down
list is"). Headless Chrome through the driver base (tests/helpers/
studio_roles_model.py; skipped without one), over a fresh home with the
shipped lineups and no provider set up:

1. the Inspector's MODEL strip with nothing selected names the main card and,
   with no live list, says why in one line with its fix (3.4.1.3: no provider
   is set up -> Setup), the Models panel every provider's line; the picker it
   opens says the same and keeps its last row, never an empty list;
2. Refresh over a provider that answers and one past the time box: one outcome
   line each under the strip, and the picker lists the two answered models;
3. a selected card: the strip names the model it resolves to (the graph's);
   a model picked there is saved (`GET lineup` reads `models.preference`) and
   the card's pill follows; Test shows the stubbed probe inline;
4. a card's pill click (and Enter on a selected card) selects it and focuses
   the strip's field;
5. "change the bio's model": the bio form, MODELS first, its field focused,
   the picker folded until the field is clicked (then one row per catalog model).
Run: python -m tests.test_studio_roles_model
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
    info = driver_got(ctx, "tests.helpers.studio_roles_model", why="the Roles model checks need headless Chrome",
                      cache=_RUN, timeout=400, tail=500, stdin=False)
    return info


@test
def test_the_strip_says_why_the_list_is_empty_and_offers_refresh(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"nothing selected: the main card, got {got.get('main_strip')!r}", got.get("main_strip") == "boss#0")
    ctx.check(f"no live list: why in one line and its fix, got {got.get('empty_why')!r} / {got.get('looked')!r}",
              "no provider is set up here yet" in str(got.get("empty_why")) and got.get("empty_setup") is True
              and "Looked at" in str(got.get("looked")) and "OpenRouter: not configured" in str(got.get("looked")))
    why, last, n = (got.get("empty_dialog") or ["", False, -1])
    ctx.check(f"the picker says it too and keeps its last row, got {got.get('empty_dialog')}",
              "no provider is set up here yet" in why and last is True and n == 0)


@test
def test_refresh_shows_one_line_per_provider_and_fills_the_select(ctx: Ctx):
    got = _got(ctx)
    outcomes = got.get("outcomes") or []
    # a slow runner (Windows CI) may read the page after Slowpoke's late answer replaced its timed-out line:
    # either line proves one outcome per provider
    ctx.check(f"one outcome line each, got {outcomes}", len(outcomes) == 2 and outcomes[0] == "FakeRouter: ok, 2 models"
              and outcomes[1] in ("Slowpoke: timed out after 1.5 s (still asking: its list lands when it answers)", "Slowpoke: ok, 1 model"))
    ctx.check(f"the picker lists the answered models, got {got.get('live_options')}", got.get("live_options") == ["or:fakeco/alpha-1", "or:fakeco/beta-2"])
    ctx.check(f"and says when, got {got.get('refreshed')!r}", got.get("refreshed") == "refreshed just now")


@test
def test_a_pick_in_the_strip_saves_the_card_and_its_pill_follows(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"runs on: what the card resolves to, got {got.get('runs_on')!r} / graph {got.get('graph_model')!r}",
              got.get("runs_on") and got.get("runs_on") == got.get("graph_model"))
    ctx.check(f"GET lineup reads the card's own model, got {got.get('saved_pref')!r}", got.get("saved_pref") == "or:fakeco/beta-2")
    ctx.check(f"the card's pill follows, got {got.get('pill_after')!r}", got.get("pill_after") == "beta-2")
    ctx.check(f"Test shows the probe inline, got {got.get('probe')!r}", got.get("probe") == "fakeco/beta-2: ok in 42 ms")


@test
def test_the_pill_and_enter_focus_the_strips_select(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the pill's title says it, got {got.get('pill_title')!r}", "click to change it" in str(got.get("pill_title")))
    ctx.check(f"a pill click selects its card and focuses the select, got {got.get('pill_focus')!r}",
              got.get("pill_focus") and got.get("pill_focus") == got.get("pill_card"))
    ctx.check(f"Enter on the selected card does the same, got {got.get('enter_focus')!r}", got.get("enter_focus") == "worker#0")


@test
def test_the_bio_form_puts_models_first_with_the_table_folded(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"MODELS is the first section, above the description, got {got.get('bio_first_section')!r}",
              got.get("bio_first_section") == "MODELS" and got.get("models_before_description") is True)
    ctx.check("the link focused the bio's model select", got.get("bio_focus") is True)
    ctx.check(f"the table folded, then unfolded by more..., got {got.get('picker_folded')} / {got.get('picker_rows')}",
              got.get("picker_folded") == 0 and got.get("picker_rows") == 2 and got.get("dialogs") == 0)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
