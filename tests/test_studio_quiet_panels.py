"""tests.test_studio_quiet_panels -- Halo 3.3.2.0 "Quiet Studio" round R3: quieter panels, one thing per section,
(a density setting, removed in 3.6.0.1) (the owner, 2026-10-27: "the visuals in studio are too cluttered"). Headless Chrome at 1280 x 800
through tests/helpers/studio_quiet_panels.py (skipped without one), over a seeded scratch home; no provider
request, no model call:

1. one thing per section: on a fresh browser each of Session, Agents (Cast) and Packs opens on its main panel (Live,
   Canvas, Installed), its box >= 60 % of the stage, every other panel closed: a button in the view bar (3.6.0.0 R0a;
   strips at the foot before);
2. the ornament on one panel at a time: one `.panel.focused` (the main one until a click), one set of HUD
   brackets, one mono data line, no about line in any panel; a click moves it; the panel's ? opens its help on
   the about line and toggles it shut;
3. (on Agents -> 3 · Map, the drawer of what they think and say; 3.6.0.0 R5) a drawer opens on the main panel's right (the main panel gives up that
   width, as tall as before, one 12 px gap between them) and gives it back when closed; the drawer is kept across a
   reload with no "custom layout" badge, Reset layout returns to the default;
4. no density setting (3.6.0.1: the header's three-lines button changed a few pixels and read as broken; it went
   with its setting): the header has no density button and no hole where it was, at 1280 and at 700 px wide; a
   browser that saved `halo.studio.density = compact` under 3.6.0.0 opens with the default tokens (`--pad`, the
   stage's gap, the title line, the body text) and no `data-density` on <html>; the palette has no Density command.
Plus source pins: no about line in the panel frame, no compact token set and no density store.
Run: python -m tests.test_studio_quiet_panels
"""
from __future__ import annotations

TIER = "full"  # headless Chrome: the full tier

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.runner import Ctx, new_registry, print_results, run_all  # noqa: E402
from tests.helpers.driver_got import got as driver_got  # noqa: E402

test, TESTS = new_registry()
REPO = Path(__file__).resolve().parent.parent
UI = REPO / "halo_harness" / "studio" / "ui" / "src"
_RUN: dict = {}
PRIMARY = {"session": "session-live", "roles": "map-main",  # 3.3.16.0 R1: roles, Agents' door; 3.6.0.0 R5: it lands on the Map
           "packs": "pm-installed"}


def _got(ctx: Ctx) -> dict:
    info = driver_got(ctx, "tests.helpers.studio_quiet_panels", why="the quiet panel checks need headless Chrome",
                      cache=_RUN, key="run", timeout=480, tail=600)
    return info


@test
def test_the_source_is_quiet(ctx: Ctx):
    panel = (UI / "lib" / "workspace" / "Panel.tsx").read_text(encoding="utf-8")
    ctx.check("the panel frame draws no about line", "panel-about" not in panel and "{spec.about}</" not in panel)
    ctx.check("the brackets and the data line only on the focused panel",
              '{focused && <span className="hud-brackets"' in panel and "{focused && (" in panel and 'data-testid="panel-help-btn"' in panel)
    # 3.6.0.1: the density setting is gone (the header's three-lines button changed a few pixels); one token set, no
    # store (tests/test_studio_no_density_setting.py pins the rest of the removal)
    css = (UI / "styles" / "tokens.css").read_text(encoding="utf-8")
    ctx.check("tokens.css has no compact set", 'data-density="compact"' not in css)
    ctx.check("no density store (nothing reads halo.studio.density)", not (UI / "lib" / "density.ts").exists())
    specs = {sid: pid for sid, pid in PRIMARY.items()}
    src = "\n".join(p.read_text(encoding="utf-8") for p in (UI / "routes").rglob("*.tsx"))
    for sid, pid in specs.items():
        ctx.check(f"{sid}: {pid} is the primary", re.search(rf'panel\("{pid}", \{{ title: "[^"]+", primary: true,', src) is not None
                  or re.search(rf'\{{ id: "{pid}", testid: "{pid}-panel", title: "[^"]+", role: "main",', src) is not None)


@test
def test_one_thing_per_section(ctx: Ctx):
    got = _got(ctx)
    for sid, pid in PRIMARY.items():
        cover = (got.get("cover") or {}).get(sid) or 0
        ctx.check(f"{sid}: {pid} covers >= 60 % of the stage at 1280 x 800, got {cover}", cover >= 0.6)
        state = dict((got.get("state") or {}).get(sid) or [])
        others = {k: v for k, v in state.items() if k != pid and not k.endswith("-builder")}  # 3.6.0.0 R5: the builder is a dock
        ctx.check(f"{sid}: the main panel open, every other panel closed in the view bar, got {state}",
                  state.get(pid) == "open" and others and set(others.values()) == {"closed"})


@test
def test_the_ornament_on_one_panel(ctx: Ctx):
    got = _got(ctx)
    for sid, pid in PRIMARY.items():
        orn = (got.get("ornament") or {}).get(sid)
        ctx.check(f"{sid}: one focused panel (the main one), one set of brackets, one data line, no about line, got {orn}",
                  orn == [[pid], 1, 1, 1, 0])
    ctx.check(f"a click moves it, got {got.get('ornament_click')}", got.get("ornament_click") == [["map-drawer"], 1, 1, 1, 0])
    ctx.check(f"the ? opens the help on the about line, got {got.get('help_first')!r} / {got.get('about_title')!r}",
              bool(got.get("help_first")) and got.get("help_first") == got.get("about_title"))
    ctx.check(f"the ? again closes it, got {got.get('help_toggled')}", got.get("help_toggled") == "closed")


@test
def test_a_drawer_opens_beside_the_main_panel_and_is_kept(ctx: Ctx):
    got = _got(ctx)
    mb, ao, mo, back = (got.get(k) or [0, 0, 0, 0] for k in ("map_before", "att_open", "map_open", "map_back"))
    # 3.6.0.0 R5: on the Map the builder's dock sits under the main panel and the drawer spans both (its text wraps
    # in the narrower column, so the main panel may give up a few px of height to it)
    ctx.check(f"the drawer sits right of the map (one 12 px gap), from its top past its foot, the map narrower by its width, got {mb} {ao} {mo}",
              ao[1] + ao[3] >= mo[1] + mo[3] and mo[2] < mb[2] and abs((mo[0] + mo[2] + 12) - ao[0]) <= 2 and ao[1] == mb[1] == mo[1])
    ctx.check(f"closed again, the tree has its width back, no badge, got {back} {got.get('custom_after')}", back == mb and got.get("custom_after") is False)
    ctx.check(f"opened: saved, kept across a reload, no badge, got {got.get('map_mine')} {got.get('map_reload')} {got.get('badge')}",
              got.get("key") is True and got.get("map_mine") != got.get("map_default") and got.get("map_reload") == got.get("map_mine") and got.get("badge") is False)
    ctx.check(f"Reset layout: the default again, got {got.get('reset')} {got.get('map_reset')} {got.get('cover_reset')}",
              got.get("reset") is True and got.get("map_reset") == got.get("map_default") and (got.get("cover_reset") or 0) >= 0.6)


@test
def test_no_density_setting(ctx: Ctx):
    """3.6.0.1 (rewritten from 3.3.2.0's test_density, which drove the toggle this release removes)."""
    got = _got(ctx)
    fresh = got.get("fresh") or []
    ctx.check(f"the Instrument scale (3.3.15.0 L1): --pad 12px, a 12 px stage gap, a 40 px title line, 13 px text, no data-density on <html>, got {fresh}",
              fresh == ["", "12px", "12px", 40, "13px"])
    for key, width in (("header", 1280), ("header_narrow", 700)):
        h = got.get(key) or [None] * 5
        ctx.check(f"at {width} px: no density button, the palette door and the theme menu one header gap apart, the theme menu "
                  f"last and flush with the header's padding (no hole where the button was), got {h}",
                  h[0] == 0 and h[1] == h[2] and h[2] > 0 and abs(h[3]) <= 1 and h[4] is True)
    ctx.check(f"a browser that saved halo.studio.density = compact under 3.6.0.0 opens with the default tokens, got {got.get('saved_compact')} {got.get('html_attr')}",
              got.get("saved_compact") == fresh and got.get("html_attr") is False)
    ctx.check(f"the palette offers no Density command, got {got.get('palette')}", got.get("palette") == [])


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
