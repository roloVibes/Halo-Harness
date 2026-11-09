"""tests.test_studio_themes -- one `theme` key for the terminal and Studio (Halo 3.3.12.0 R1). Headless Chrome through
tests/helpers/studio_themes.py (skipped without one) over a fresh scratch home; no provider request, no model call;
every theme write lands in the scratch config.json:

1. a fresh page is instrument (3.3.15.0 R4): `data-theme="instrument"`, its --bg on a dark AND a light system, the
   menu's and Settings -> Themes' mark on instrument (it followed the system before);
2. the header's menu lists Follow the system and the eleven, each with a swatch row; picking ember writes `theme:
   ember` to config.json and flips the page's `data-theme`; a reload keeps it;
3. Settings -> Themes: the eleven rows (and Follow), the swatches in the colours the API gives, Preview on hover with
   config.json untouched, Esc reverts, the current mark moves on a click, Daltonized writes `<id>-daltonized`;
4. "Follow the system" writes `theme: auto` (R4; it removed the key before): the page is `auto`, instrument on a dark
   system and paper on a light one, across a reload, the menu's mark on it;
5. (3.3.12.0 R2) the fixture pack enabled: `pack-theme/nightshade` in the menu and on Settings -> Themes under
   "pack-theme"; picking it writes the key and the page's --accent is the fixture's token; a reload with the page's
   scripts off is already drawn in it (the server's inline rule: no frame of the default); disabling the pack through the Pack
   Manager's route restores midnight, the theme saved before, on the open page.
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
TWELVE = ["auto", "claude-dark", "claude-light", "holo", "instrument", "paper", "midnight", "ember", "forest", "slate", "dusk", "dawn"]


def _got(ctx: Ctx) -> dict:
    return driver_got(ctx, "tests.helpers.studio_themes", why="the theme checks need headless Chrome", cache=_RUN, timeout=300, tail=600)


@test
def test_a_fresh_page_is_instrument(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"data-theme instrument (3.3.15.0 R4), got {got.get('fresh_theme')!r}", got.get("fresh_theme") == "instrument")
    ctx.check(f"instrument on a dark AND a light system, got {got.get('fresh_bg_dark')} {got.get('fresh_bg_light')} {got.get('fresh_light_load')}",
              got.get("fresh_bg_dark") == "#07090c" and got.get("fresh_bg_light") == "#07090c"
              and got.get("fresh_light_load") == ["instrument", "#07090c"])
    ctx.check(f"Settings -> Themes marks instrument and says it is the default, got {got.get('fresh_current')} {got.get('fresh_cli')!r}",
              got.get("fresh_current") == ["instrument"] and "Halo's default, instrument" in str(got.get("fresh_cli")))


@test
def test_the_header_menu_writes_the_one_key(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Follow the system and the eleven, got {got.get('menu_ids')}", got.get("menu_ids") == TWELVE)
    ctx.check(f"a swatch row per palette, got {got.get('menu_swatches')}", got.get("menu_swatches") == 11)
    ctx.check(f"nothing saved: the mark on instrument, not Follow, got {got.get('menu_checked')}", got.get("menu_checked") == ["instrument"])
    ctx.check(f"ember: config.json theme ember, the page's data-theme ember, got {got.get('pick_saved')} {got.get('pick_theme')}",
              got.get("pick_saved") == "ember" and got.get("pick_theme") == "ember" and got.get("pick_bg") == "#140a08")
    ctx.check(f"a reload keeps it, got {got.get('reload_theme')!r}", got.get("reload_theme") == "ember")


@test
def test_the_settings_themes_page(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Follow and the eleven rows, got {got.get('page_rows')}", got.get("page_rows") == TWELVE)
    ctx.check(f"the door's page word left the address, got {got.get('page_search')!r}", "page=" not in str(got.get("page_search")))
    ctx.check(f"ember marked current, got {got.get('page_current')}", got.get("page_current") == ["ember"])
    ctx.check(f"77 chips in the API's colours, off: {got.get('chips_off')}", got.get("chips_checked") == 77 and got.get("chips_off") == [])
    ctx.check(f"the pointer on paper previews it, config.json untouched, got {got.get('hover_theme')} {got.get('hover_saved')}",
              got.get("hover_theme") == "paper" and got.get("hover_saved") == "ember")
    ctx.check(f"Esc puts ember back, got {got.get('esc_theme')!r}", got.get("esc_theme") == "ember")
    ctx.check(f"a click saves dusk and the mark moves, got {got.get('dusk_saved')} {got.get('dusk_current')}",
              got.get("dusk_saved") == "dusk" and got.get("dusk_current") == ["dusk"] and got.get("dusk_theme") == "dusk")
    ctx.check(f"Daltonized: dusk-daltonized saved, the page's accent the daltonized one, got {got.get('dal_saved')} {got.get('dal_accent')}",
              got.get("dal_saved") == "dusk-daltonized" and got.get("dal_accent") == got.get("dal_want"))


@test
def test_follow_the_system_writes_auto(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"theme: auto saved, the page auto, across a reload, got {got.get('follow_saved')} {got.get('follow_theme')} {got.get('follow_reload')}",
              got.get("follow_saved") == "auto" and got.get("follow_theme") == "auto" and got.get("follow_reload") == "auto")
    ctx.check(f"it follows: instrument on dark, paper on light, got {got.get('follow_bg_dark')} {got.get('follow_bg_light')}",
              got.get("follow_bg_dark") == "#07090c" and got.get("follow_bg_light") == "#f7f3ea")
    ctx.check(f"the menu's mark on Follow the system, got {got.get('follow_checked')}", got.get("follow_checked") == ["auto"])


@test
def test_a_pack_palette_in_the_menu_the_page_and_the_first_paint(ctx: Ctx):
    got = _got(ctx)
    night = "pack-theme/nightshade"
    ctx.check(f"the fixture installed and enabled, got {got.get('pack_installed')}", got.get("pack_installed") is True)
    ctx.check(f"the menu: its two palettes under pack-theme, got {got.get('pack_menu_group')} {got.get('pack_menu_head')!r}",
              got.get("pack_menu_group") == [night, "pack-theme/linen"] and str(got.get("pack_menu_head", "")).startswith("pack-theme"))
    ctx.check(f"picked: the key and the page's --accent, got {got.get('pack_saved')} {got.get('pack_accent')}",
              got.get("pack_saved") == night and got.get("pack_accent") == "#b48cff")
    ctx.check(f"Settings -> Themes: under pack-theme, current, got {got.get('pack_page_rows')} {got.get('pack_page_current')}",
              got.get("pack_page_rows") == [night, "pack-theme/linen"] and got.get("pack_page_current") == [night]
              and str(got.get("pack_page_head", "")).startswith("pack-theme"))
    ctx.check(f"the first paint, scripts off: the pack palette already, got {got.get('first_theme')} {got.get('first_accent')} "
              f"{got.get('first_bg')} app ran {got.get('first_app_ran')}", got.get("first_theme") == night and got.get("first_accent") == "#b48cff"
              and got.get("first_bg") == "#0d0b14" and got.get("first_app_ran") is False and got.get("first_inline_vars") == 0)
    ctx.check(f"disabled through the route: midnight back on the page, got {got.get('off_saved')} {got.get('off_theme')} {got.get('off_accent')} "
              f"inline '{got.get('off_inline_accent')}' rows {got.get('off_rows')}",
              got.get("off_saved") == "midnight" and got.get("off_theme") == "midnight" and got.get("off_accent") == "#5b9dff"
              and got.get("off_inline_accent") == "" and got.get("off_rows") == 12)
    ctx.check(f"and the disable said so, got {got.get('off_lines')}", any("restored midnight" in ln for ln in got.get("off_lines") or []))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
