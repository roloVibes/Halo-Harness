"""tests.test_studio_settings -- the Settings section (Halo 3.3.3.0 R2, Alt+8 since 3.3.13.0 R2: every config.json key from one
catalog). Headless Chrome through tests/helpers/studio_settings.py (skipped without one), over a fresh scratch home
with one placeholder secret saved; no provider request, no model call:

1. Alt+8 opens Settings with nothing open over it, on General, no panels;
2. every group page lists exactly the catalog's rows for that group (count and `data-key` set equal), in the
   catalog's group order;
3. a bool toggled (config.json has it, the flash names the effect), an enum picked, a number set (its
   `halo config set` footer follows), Reset (the key gone from config.json, the default marker back);
4. a mapping that is not JSON: the problems line under its editor, config.json unchanged;
5. the search box narrows to the rows matching across groups, a caption per group;
6. the door `?mode=settings&group=local` lands on Local and drops the group word from the address;
7. the secret row never shows its value; the palette's "Settings: Host port" opens Local with the row lit.
Run: python -m tests.test_studio_settings
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
    info = driver_got(ctx, "tests.helpers.studio_settings", why="the Settings checks need headless Chrome",
                      cache=_RUN, timeout=300, tail=600)
    return info


@test
def test_alt8_opens_settings_with_nothing_over_it(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"Alt+6 is Settings (3.3.16.0 R1), got {got.get('alt8_section')!r}", str(got.get("alt8_section")).startswith("Settings"))
    ctx.check(f"no help, no Start here, no dialog after 2 s, got {got.get('alt8_open')}", got.get("alt8_open") == [False, False, 0])
    ctx.check(f"it lands on General, got {got.get('alt8_page')!r}", got.get("alt8_page") == "general")
    ctx.check(f"no panel workspace, got {got.get('alt8_panels')}", got.get("alt8_panels") == 0)


@test
def test_every_group_page_lists_the_catalog_rows(ctx: Ctx):
    from halo_harness.settings_catalog import GROUPS, rows
    got = _got(ctx)
    ctx.check(f"the rail is the catalog's groups in order, got {got.get('rail_groups')}", got.get("rail_groups") == [g for g, _ in GROUPS if g != "from_packs"])  # 3.4.0.0 B2: From packs only with rows
    pages = got.get("pages") or {}
    for gid, _title in GROUPS:
        want = [r.key for r in rows() if r.group == gid and r.key != "studio.alerts"]  # 3.4.1.1 (64): the Alerts block's
        seen = pages.get(gid) or []
        ctx.check(f"{gid}: {len(want)} rows, the catalog's keys in its order, got {len(seen)}", seen == want)


@test
def test_a_change_saves_at_once_and_reset_brings_the_default_back(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the bool toggled off in config.json, got {got.get('toggle_config')!r}", got.get("toggle_config") is False)
    ctx.check(f"its flash names the effect, got {got.get('toggle_flash')!r}", got.get("toggle_flash") == "saved · takes effect in the next session")
    ctx.check("the default marker left the row", got.get("toggle_default_gone") is True)
    ctx.check(f"the enum picked, got {got.get('enum_config')!r} {got.get('enum_flash')!r}", got.get("enum_config") == "all"
              and got.get("enum_flash") == "saved · takes effect now")
    ctx.check(f"the number set, got {got.get('number_config')!r} {got.get('number_flash')!r}", got.get("number_config") == 7431
              and got.get("number_flash") == "saved · takes effect on the next launch")
    ctx.check(f"the footer is its halo config set line, got {got.get('number_cli')!r}", got.get("number_cli") == "halo config set host.port 7431")
    ctx.check(f"Reset: the key gone from config.json, the marker back, Reset off, got {got.get('reset_config')} {got.get('reset_off')}",
              got.get("reset_marker") is True and got.get("reset_config") is False and got.get("reset_off") is True)


@test
def test_a_bad_mapping_shows_its_problem_and_writes_nothing(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"the problems line under the editor, got {got.get('json_problems')!r}",
              str(got.get("json_problems")).startswith("openai.dialect_overrides: not valid JSON"))
    ctx.check("config.json byte for byte as it was", got.get("json_unchanged") is True)
    ctx.check(f"one problems list on the page, got {got.get('json_problem_rows')}", got.get("json_problem_rows") == 1)


@test
def test_the_search_narrows_across_groups(ctx: Ctx):
    from halo_harness.settings_catalog import GROUP_TITLES, rows
    got = _got(ctx)
    want = [r.key for r in rows() if "port" in f"{r.key} {r.title} {r.help} {GROUP_TITLES[r.group]}".lower()]
    ctx.check(f"the rows matching port across groups, got {got.get('search_keys')}", got.get("search_keys") == want and len(want) >= 3)
    groups = list(dict.fromkeys(r.group for r in rows() if r.key in want))
    ctx.check(f"a caption per group, got {got.get('search_groups')}", got.get("search_groups") == groups and len(groups) >= 2)


@test
def test_the_door_and_the_secret_and_the_palette(ctx: Ctx):
    got = _got(ctx)
    ctx.check(f"?mode=settings&group=local lands on Local, got {got.get('door_page')!r}", got.get("door_page") == "local")
    ctx.check(f"the group word left the address, got {got.get('door_search')!r}", "group=" not in str(got.get("door_search")))
    ctx.check(f"the page is remembered on a plain load, got {got.get('door_remembered')!r}", got.get("door_remembered") == "local")
    ctx.check("the secret row says set, hidden, as an empty password field", got.get("secret_masked") is True
              and got.get("secret_type") == "password" and got.get("secret_value") == "")
    ctx.check("the secret is nowhere on the page", got.get("secret_seen") is False)
    ctx.check(f"the palette entry opens Local with Host port lit, got {got.get('palette_page')!r} {got.get('palette_lit')!r}",
              got.get("palette_page") == "local" and got.get("palette_lit") == "host.port")


@test
def test_the_source_keeps_the_shape(ctx: Ctx):
    """No Chrome needed: the files the round names, each under the cap, and Settings is paged after Setup on Alt+8."""
    ui = REPO / "halo_harness" / "studio" / "ui" / "src"
    names = ["Settings.tsx", "SettingsRail.tsx", "SettingsPage.tsx", "Row.tsx", "pages.ts", "store.ts", "door.ts"]
    names += [f"fields/{n}.tsx" for n in ("Toggle", "Select", "Number", "Text", "ListEditor", "JsonEditor")]
    for name in names:
        p = ui / "routes" / "settings" / name
        ctx.check(f"{name} exists and is under 250 lines", p.is_file() and len(p.read_text(encoding="utf-8").splitlines()) < 250)
    routes = (ui / "routes" / "index.tsx").read_text(encoding="utf-8")
    ctx.check("Settings' entry is paged, after Setup, on Alt+6 (3.3.16.0 R1)", 'id: "settings", title: "Settings", kbd: "Alt+6", blurb: "Every config key, one page per group", '
              'panels: [], paged: true, view: SettingsView' in routes and routes.index('id: "setup"') < routes.index('id: "settings"'))
    pages = (ui / "routes" / "settings" / "pages.ts").read_text(encoding="utf-8")
    ctx.check("the remembered page is halo.studio.settings.page", '"halo.studio.settings.page"' in pages)
    door = (ui / "routes" / "settings" / "door.ts").read_text(encoding="utf-8")
    ctx.check("the door opens no help", "openHelp" not in door)


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
