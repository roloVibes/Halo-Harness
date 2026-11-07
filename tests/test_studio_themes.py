"""tests.test_studio_themes -- one `theme` key for the terminal and Studio (Halo 3.3.12.0 R1). Headless Chrome through
tests/helpers/studio_themes.py (skipped without one) over a fresh scratch home; no provider request, no model call;
every theme write lands in the scratch config.json:

1. a fresh page follows the system: `data-theme="auto"`, holo on a dark system, paper on a light one;
2. the header's menu lists Follow the system and the ten, each with a swatch row; picking ember writes `theme:
   ember` to config.json and flips the page's `data-theme`; a reload keeps it;
3. Settings -> Themes: the ten rows (and Follow), the swatches in the colours the API gives, Preview on hover with
   config.json untouched, Esc reverts, the current mark moves on a click, Daltonized writes `<id>-daltonized`;
4. "Follow the system" removes the key and the page is `auto` again, across a reload.
Run: python -m tests.test_studio_themes
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
ELEVEN = ["auto", "claude-dark", "claude-light", "holo", "paper", "midnight", "ember", "forest", "slate", "dusk", "dawn"]


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_themes", why="the theme checks need headless Chrome", cache=_RUN, timeout=300, tail=600)


@test
def test_a_fresh_page_follows_the_system(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"data-theme auto, got {got.get('fresh_theme')!r}", got.get("fresh_theme") == "auto")
    ctx.check(f"holo on a dark system, paper on a light one, got {got.get('fresh_bg_dark')} {got.get('fresh_bg_light')}",
              got.get("fresh_bg_dark") == "#070b14" and got.get("fresh_bg_light") == "#f7f3ea")


@test
def test_the_header_menu_writes_the_one_key(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Follow the system and the ten, got {got.get('menu_ids')}", got.get("menu_ids") == ELEVEN)
    ctx.check(f"a swatch row per palette, got {got.get('menu_swatches')}", got.get("menu_swatches") == 10)
    ctx.check(f"ember: config.json theme ember, the page's data-theme ember, got {got.get('pick_saved')} {got.get('pick_theme')}",
              got.get("pick_saved") == "ember" and got.get("pick_theme") == "ember" and got.get("pick_bg") == "#140a08")
    ctx.check(f"a reload keeps it, got {got.get('reload_theme')!r}", got.get("reload_theme") == "ember")


@test
def test_the_settings_themes_page(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Follow and the ten rows, got {got.get('page_rows')}", got.get("page_rows") == ELEVEN)
    ctx.check(f"the door's page word left the address, got {got.get('page_search')!r}", "page=" not in str(got.get("page_search")))
    ctx.check(f"ember marked current, got {got.get('page_current')}", got.get("page_current") == ["ember"])
    ctx.check(f"70 chips in the API's colours, off: {got.get('chips_off')}", got.get("chips_checked") == 70 and got.get("chips_off") == [])
    ctx.check(f"the pointer on paper previews it, config.json untouched, got {got.get('hover_theme')} {got.get('hover_saved')}",
              got.get("hover_theme") == "paper" and got.get("hover_saved") == "ember")
    ctx.check(f"Esc puts ember back, got {got.get('esc_theme')!r}", got.get("esc_theme") == "ember")
    ctx.check(f"a click saves dusk and the mark moves, got {got.get('dusk_saved')} {got.get('dusk_current')}",
              got.get("dusk_saved") == "dusk" and got.get("dusk_current") == ["dusk"] and got.get("dusk_theme") == "dusk")
    ctx.check(f"Daltonized: dusk-daltonized saved, the page's accent the daltonized one, got {got.get('dal_saved')} {got.get('dal_accent')}",
              got.get("dal_saved") == "dusk-daltonized" and got.get("dal_accent") == got.get("dal_want"))


@test
def test_follow_the_system_clears_the_key(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the key gone, the page auto, across a reload, got {got.get('follow_saved')} {got.get('follow_theme')} {got.get('follow_reload')}",
              got.get("follow_key_gone") is True and got.get("follow_theme") == "auto" and got.get("follow_reload") == "auto")


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
