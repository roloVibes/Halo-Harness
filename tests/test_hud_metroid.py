"""tests.test_hud_metroid -- the Metroid skin (Halo 2.0.8 theme pack, round
2): the declaration, the shared HUD checks (width sweep, cascade, faces,
ASCII fallback), the energy-tank meter, the five area variants, the engine
seams (meter_cells, variants, turns, area), `/metroid <area>` and the
Textual chrome (map-grid border classes, visor input frame, wizard variant
list). The toggle contract itself is pinned for all three games in
tests/test_theme_toggles.py and is NOT repeated here beyond "bare /metroid
is unchanged after an area was chosen".
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from rich.cells import cell_len

from halo_harness import theme as theme_mod
from halo_harness import theme_toggle as tt
from halo_harness.tui.hud import HudField, skin_for
from halo_harness.tui.theme import variables_for
from halo_harness.tui.theme_metroid import AREAS
from tests.helpers import hud_skin_checks as chk

test, TESTS = new_registry()
AREA_NAMES = ("crateria", "brinstar", "norfair", "maridia", "tourian")


@contextlib.contextmanager
def _scoped():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    tmp = Path(tempfile.mkdtemp(prefix="halo-metroid-"))
    os.environ["BRIDGE_TEST_HOME"] = str(tmp)
    os.environ["BRIDGE_STATE_DIR"] = str(tmp / ".halo")
    try:
        yield tmp / ".halo"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _cfg() -> dict:
    return theme_mod.load_config()


def _tanks(frac: float, ascii_mode: bool = False, width: int = 120) -> tuple:
    fields = chk.sample_fields()
    fields["context"] = HudField(f"{frac * 100:.0f}%", f"{frac * 100:.0f}%", "ok", frac)
    row = chk.lines(skin_for("metroid"), width, ascii_mode=ascii_mode, fields=fields)[1]
    return row.count("#" if ascii_mode else "■"), row


# ---- the declaration -----------------------------------------------------------

@test
def test_metroid_skin_is_a_declaration_on_the_shared_engine(ctx: Ctx):
    skin = skin_for("metroid")
    ctx.check("metroid has a skin", skin is not None and skin.name == "metroid")
    chk.check_declaration(ctx, skin)
    order = [s.slot for s in skin.segments]
    ctx.check(f"panel order is energy reserve missiles supers visor cost beam area, got {order}",
              order == ["context", "tokens", "turns", "tools", "face", "cost", "providers", "area"])
    labels = [s.label for s in skin.segments]
    ctx.check(f"panel captions, got {labels}",
              labels == ["ENERGY", "RESERVE", "MISSILE", "SUPER", "", "COST", "BEAM", "AREA"])
    ctx.check("ten energy tanks, three rows, light (non-heavy) borders",
              skin.meter_cells == 10 and skin.rows == 3 and not skin.heavy_borders)
    ctx.check("map-grid borders: dashed, ascii without truecolor",
              skin.panel_border == "dashed" and skin.panel_border_ascii == "ascii")
    ctx.check("visor frame: two glyphs, two ascii fallbacks",
              len(skin.input_frame) == 2 and len(skin.input_frame_ascii) == 2
              and all(g.isascii() for g in skin.input_frame_ascii) and not any(g.isascii() for g in skin.input_frame))
    ctx.check("area is never dropped, the keepers stay", "area" not in skin.drop_order)
    ctx.check("metroid no longer rides the placeholder accent", skin_for("metroid") and
              __import__("halo_harness.tui.hud", fromlist=["x"]).accent_for("metroid") is None)


@test
def test_shared_width_sweep_cascade_faces_and_ascii_fallback(ctx: Ctx):
    skin = skin_for("metroid")
    chk.check_width_sweep(ctx, skin)
    chk.check_width_sweep(ctx, skin, ascii_mode=True)
    chk.check_cascade_follows_drop_order(ctx, skin)
    chk.check_faces(ctx, skin)
    chk.check_ascii_fallback(ctx, skin)
    for area in AREA_NAMES:  # a variant changes colours and a glyph, never the geometry
        v = skin_for("metroid", area)
        ctx.check(f"{area}: same widths as the base skin",
                  all([cell_len(r) for r in chk.lines(v, w)] == [cell_len(r) for r in chk.lines(skin, w)]
                      for w in (46, 66, 80, 100, 140)))


@test
def test_narrow_cascade_keeps_phase_context_cost_area_mode(ctx: Ctx):
    skin = skin_for("metroid")
    fields = {k: v for k, v in chk.sample_fields().items() if k != "model"}
    for width in (46, 50, 66, 80):
        text = "\n".join(chk.lines(skin, width, fields=fields))
        for needle in ("62%", "$0.0123", "writing", "auto", "project"):
            ctx.check(f"{width}: {needle!r} kept", needle in text)
    ctx.check("46: the visor face kept", "<=>" in "\n".join(chk.lines(skin, 46, "writing")) or "-o-" in "\n".join(chk.lines(skin, 46)))
    compact = chk.lines(skin, 40)[0]
    for needle in ("62%", "$0.0123", "writing", "auto", "proj"):
        ctx.check(f"compact line keeps {needle!r}", needle in compact)
    wide = "\n".join(chk.lines(skin, 140))
    for label in ("ENERGY", "RESERVE", "MISSILE", "SUPER", "COST", "BEAM", "AREA"):
        ctx.check(f"wide shows {label}", label in wide)
    ctx.check("80 columns keeps ENERGY with its tanks", "■■■■■■□□□□ 62%" in "\n".join(chk.lines(skin, 80)))


# ---- the energy tanks --------------------------------------------------------------

@test
def test_energy_tanks_follow_remaining_context_in_tens(ctx: Ctx):
    for frac, want in ((0.0, 0), (0.10, 1), (0.55, 6), (1.0, 10)):
        on, row = _tanks(frac)
        off = row.count("□")
        ctx.check(f"{frac:.0%}: {want} full tanks and {10 - want} empty, got {on}/{off}", (on, off) == (want, 10 - want))
        ctx.check(f"{frac:.0%}: the exact number sits beside the tanks", f"{frac * 100:.0f}%" in row)
        a_on, a_row = _tanks(frac, ascii_mode=True)
        ctx.check(f"{frac:.0%}: ascii tanks are # and . ({a_on} full)", a_on == want and a_row.count(".") >= 10 - want)
    on, row = _tanks(0.62, width=46)
    ctx.check("46 columns: the tanks give way, the number stays", on == 0 and "62%" in row)


@test
def test_empty_tanks_are_dimmed_through_the_skin_style(ctx: Ctx):
    from halo_harness.tui.hud_render import render_hud
    skin = skin_for("metroid")
    text = render_hud(skin, chk.sample_fields(), width=120)
    styles = {str(span.style) for span in text.spans}
    ctx.check("the empty-tank style is applied to some span", skin.styles["meter_off"] in styles)


# ---- counters, area panel, the engine seams ----------------------------------------------

@test
def test_counters_and_area_panel(ctx: Ctx):
    skin = skin_for("metroid")
    mid = chk.lines(skin, 140)[1]
    ctx.check("MISSILE carries the turn counter", "▲ 07" in mid)
    ctx.check("SUPER carries the tool count", "◆ 41 tools" in mid)
    ctx.check("RESERVE carries tokens left", "812k left" in mid)
    ctx.check("COST carries cost and balance", "$0.0123 · OR $12.40 left" in mid)
    ctx.check("BEAM carries the providers", "or dbx" in mid)
    ctx.check("AREA carries the cwd's last component with the branch as its sub-label", "project · main" in mid)
    ctx.check("the full cwd stays reachable in the ticker", "~/project (main)" in chk.lines(skin, 140)[2])
    for area in AREA_NAMES:
        row = chk.lines(skin_for("metroid", area), 140)[1]
        glyph = AREAS[area]["glyph"]
        ctx.check(f"{area}: its prefix glyph is in front of the area value", f"{glyph} project" in row)
    ctx.check("the area names are not printed over the cwd", all(a not in chk.lines(skin_for('metroid', a), 140)[1] for a in AREA_NAMES))
    glyphs = [AREAS[a]["glyph"] for a in AREA_NAMES]
    ctx.check("five distinct prefix glyphs", len(set(glyphs)) == 5)


@test
def test_engine_seams_are_generic_and_default_safe(ctx: Ctx):
    from halo_harness.tui.hud import Glyphs, HudSkin, Segment, SLOTS
    ctx.check("area and turns are in the shared slot vocabulary", "area" in SLOTS and "turns" in SLOTS)
    doom = skin_for("doom")
    ctx.check("doom keeps six meter cells, no variants, no map border, no visor",
              doom.meter_cells == 6 and not doom.variants and not doom.panel_border and not doom.input_frame)
    ctx.check("an unknown variant returns the base skin", skin_for("metroid", "nowhere") is skin_for("metroid"))
    ctx.check("a variant of a theme without variants returns the base skin", skin_for("doom", "crateria") is skin_for("doom"))
    ctx.check("a resolved variant is cached", skin_for("metroid", "norfair") is skin_for("metroid", "norfair"))
    g = Glyphs(h="-", v="|", tl="+", tr="+", bl="+", br="+", tee_down="+", tee_up="+", meter_on="#", meter_off=".")
    tiny = HudSkin("x", (Segment("context", "CTX", "", 7),), (), (), {"idle": ("o",)}, g, g, {}, meter_cells=3)
    from halo_harness.tui.hud_render import render_hud
    row = render_hud(tiny, {"context": HudField("50%", "50%", "ok", 0.5)}, width=60).plain.split("\n")[1]
    ctx.check(f"meter_cells=3 draws a three-cell meter, got {row!r}", "#.." in row or "##." in row)


@test
def test_five_variants_resolve_to_distinct_palettes(ctx: Ctx):
    base_keys = set(variables_for("claude-dark"))
    palettes = {a: variables_for("metroid", a) for a in AREA_NAMES}
    for area, pal in palettes.items():
        ctx.check(f"{area}: full variable set", set(pal) == base_keys)
    for key in ("bridge-bg", "bridge-accent", "bridge-border"):
        values = {p[key] for p in palettes.values()}
        ctx.check(f"{key} differs across the five areas", len(values) == 5)
    ctx.check("the default (no variant) is Crateria", variables_for("metroid") == palettes["crateria"])
    ctx.check("an unknown variant falls back to Crateria", variables_for("metroid", "nowhere") == palettes["crateria"])
    ctx.check("a variant never leaks into another theme", variables_for("doom", "norfair") == variables_for("doom"))
    ctx.check("theme.GAME_VARIANTS names exactly the five areas in order",
              theme_mod.GAME_VARIANTS["metroid"] == AREA_NAMES and tuple(AREAS) == AREA_NAMES)
    hud = {a: skin_for("metroid", a) for a in AREA_NAMES}
    for role in ("border", "label", "glyph"):
        ctx.check(f"HUD {role} colour differs across the areas", len({h.styles[role] for h in hud.values()}) == 5)
    ctx.check("HUD face styles differ across the areas", len({h.face_styles["needs_you"] for h in hud.values()}) == 5)
    def dominant(hexcolor: str) -> str:
        r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
        return "rgb"[[r, g, b].index(max(r, g, b))]
    ctx.check("the area backgrounds lean the way the names suggest",
              dominant(palettes["crateria"]["bridge-bg"]) == "b" and dominant(palettes["brinstar"]["bridge-bg"]) == "g"
              and dominant(palettes["norfair"]["bridge-bg"]) == "r"
              and dominant(palettes["maridia"]["bridge-bg"]) in "gb")


# ---- /metroid <area> and /theme metroid <area> ---------------------------------------------

@test
def test_area_is_persisted_by_the_toggle_helpers(ctx: Ctx):
    with _scoped():
        ctx.check("the default area is crateria", theme_mod.variant_for("metroid") == "crateria")
        ctx.check("doom has no variant", theme_mod.variant_for("doom") is None)
        applied = tt.set_game_variant("metroid", "norfair", "claude-light")
        ctx.check("set_game_variant applies the game theme", applied == "metroid" and _cfg()["theme"] == "metroid")
        ctx.check("... remembers the previous theme", _cfg()[tt.PREVIOUS_KEY] == "claude-light")
        ctx.check("... persists theme_variant", _cfg()["theme_variant"] == "norfair" and theme_mod.variant_for("metroid") == "norfair")
        tt.set_game_variant("metroid", "tourian", "metroid")
        ctx.check("naming an area while active re-tints without toggling off",
                  _cfg()["theme"] == "metroid" and _cfg()["theme_variant"] == "tourian"
                  and _cfg()[tt.PREVIOUS_KEY] == "claude-light")
        raised = []
        for bad in ("nowhere", "", "CRATERIA "):
            try:
                tt.set_game_variant("metroid", bad, "claude-dark")
            except ValueError as exc:
                raised.append(str(exc))
        ctx.check("an unknown area raises and lists the five", len(raised) == 3 and all("crateria" in r and "tourian" in r for r in raised))
        try:
            tt.set_game_variant("doom", "norfair", "claude-dark")
            ctx.check("a theme without variants rejects one", False)
        except ValueError as exc:
            ctx.check("a theme without variants rejects one", "no variants" in str(exc))
        theme_mod.set_config_value("theme_variant", "garbage")
        ctx.check("a corrupt persisted variant falls back to crateria", theme_mod.variant_for("metroid") == "crateria")
        ctx.check("parse_theme_args splits name and area", tt.parse_theme_args("Metroid_x  Norfair extra")[1:] == ("norfair", ["extra"]))


@test
def test_headless_area_commands_and_the_bare_toggle_after_an_area(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS, HeadlessFacade
    run = _BUILTIN_SPECS["metroid"][3]
    theme_cmd = _BUILTIN_SPECS["theme"][3]
    ctx.check("/metroid advertises its [area] argument", _BUILTIN_SPECS["metroid"][2] == "[area]")
    with _scoped():
        out = run("brinstar", HeadlessFacade(cwd=Path("."), theme="claude-light"))
        ctx.check(f"/metroid brinstar applies it: {out!r}", "brinstar" in out and _cfg()["theme"] == "metroid"
                  and _cfg()["theme_variant"] == "brinstar" and _cfg()[tt.PREVIOUS_KEY] == "claude-light")
        out = run("", HeadlessFacade(cwd=Path("."), theme="metroid"))
        ctx.check(f"bare /metroid still restores the previous theme: {out!r}",
                  _cfg()["theme"] == "claude-light" and tt.PREVIOUS_KEY not in _cfg())
        ctx.check("... and leaves the chosen area alone", _cfg()["theme_variant"] == "brinstar")
        run("", HeadlessFacade(cwd=Path("."), theme="claude-light"))
        ctx.check("bare /metroid again comes back to metroid with the same area",
                  _cfg()["theme"] == "metroid" and theme_mod.variant_for("metroid") == "brinstar")
        before = dict(_cfg())
        out = run("nowhere", HeadlessFacade(cwd=Path("."), theme="metroid"))
        ctx.check(f"an unknown area is reported, nothing written: {out!r}", "crateria" in out and _cfg() == before)
        out = theme_cmd("metroid maridia", HeadlessFacade(cwd=Path("."), theme="claude-dark"))
        ctx.check(f"/theme metroid maridia: {out!r}", "maridia" in out and _cfg()["theme"] == "metroid"
                  and _cfg()["theme_variant"] == "maridia")
        before = dict(_cfg())
        out = theme_cmd("metroid nowhere", HeadlessFacade(cwd=Path("."), theme="metroid"))
        ctx.check(f"/theme metroid nowhere is rejected, nothing written: {out!r}", "not a metroid variant" in out and _cfg() == before)
        out = theme_cmd("doom norfair", HeadlessFacade(cwd=Path("."), theme="metroid"))
        ctx.check(f"/theme doom norfair is rejected: {out!r}", "no variants" in out and _cfg() == before)
    with _scoped():  # the other games ignore a stray argument exactly as before
        out = _BUILTIN_SPECS["doom"][3]("norfair", HeadlessFacade(cwd=Path("."), theme="claude-dark"))
        ctx.check(f"/doom <anything> still toggles doom: {out!r}", _cfg()["theme"] == "doom" and "theme_variant" not in _cfg())


@test
def test_config_set_validates_the_variant_key(ctx: Ctx):
    import io
    from contextlib import redirect_stderr, redirect_stdout

    from halo_harness import cli as cli_mod

    def run(value: str) -> int:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            try:
                return cli_mod.main(["config", "set", "theme_variant", value]) or 0
            except SystemExit as e:
                return e.code or 0
    with _scoped():
        ctx.check("`halo config set theme_variant norfair` exits 0", run("norfair") == 0 and _cfg()["theme_variant"] == "norfair")
        ctx.check("an unknown variant exits 2 and is not written", run("nowhere") == 2 and _cfg()["theme_variant"] == "norfair")


# ---- inside a real app: chrome classes, visor frame, live area switch, counters -----------------

def _app(theme: str = "metroid"):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project", theme_name=theme)


def _text(widget) -> str:
    return str(widget.render())


@test
def test_map_grid_borders_and_visor_frame_follow_the_skin(ctx: Ctx):
    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(110, 30)) as pilot:
                await pilot.pause(0.1)
                bar = app.status_bar
                bar.hud_ascii = False
                app._sync_theme_chrome()
                await pilot.pause(0.05)
                glyph, right = app.query_one("#prompt-glyph"), app.query_one("#prompt-frame-r")
                ctx.check(f"3 rows under metroid, got {bar.size.height}", bar.size.height == 3)
                ctx.check("map-grid class on the app (dashed)", app.has_class("hud-border-dashed") and not app.has_class("hud-border-ascii"))
                ctx.check("no heavy class (that is DOOM's)", not app.has_class("hud-heavy"))
                ctx.check("visor class on the app", app.has_class("hud-visor"))
                ctx.check(f"left visor glyph, got {_text(glyph)!r}", "◖" in _text(glyph))
                ctx.check(f"right visor glyph, got {_text(right)!r}", "◗" in _text(right) and right.display)
                bar.hud_ascii = True
                app._sync_theme_chrome()
                await pilot.pause(0.05)
                ctx.check("no truecolor: ascii border class replaces dashed", app.has_class("hud-border-ascii") and not app.has_class("hud-border-dashed"))
                ctx.check("no truecolor: ascii visor", "(" in _text(glyph) and ")" in _text(right) and "◖" not in _text(glyph))
                app.apply_theme("doom")
                await pilot.pause(0.1)
                ctx.check("doom: no map-grid or visor classes, heavy back",
                          not any(c.startswith("hud-border-") for c in app.classes) and not app.has_class("hud-visor")
                          and app.has_class("hud-heavy"))
                ctx.check(f"doom: the prompt marker is back, got {_text(glyph)!r}", "❯" in _text(glyph) and _text(right).strip() == "")
                app.apply_theme("claude-dark")
                await pilot.pause(0.1)
                ctx.check("a normal theme carries none of the game classes",
                          not app.has_class("hud-heavy") and not app.has_class("hud-visor")
                          and not any(c.startswith("hud-border-") for c in app.classes))
    asyncio.run(body())


@test
def test_live_area_switch_recolours_the_app_and_the_hud(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _scoped():
            app = _app("claude-light")
            notes = []
            app.notify = lambda msg, **kw: notes.append((msg, kw.get("severity")))
            async with app.run_test(size=(110, 30)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "metroid", "norfair")
                await pilot.pause(0.1)
                ctx.check(f"/metroid norfair: theme and area, got {app.theme_name!r}/{app.theme_variant!r}",
                          app.theme_name == "metroid" and app.theme_variant == "norfair")
                ctx.check("the stylesheet variables are Norfair's", app.get_css_variables()["bridge-bg"] == AREAS["norfair"]["palette"]["bridge-bg"])
                ctx.check("the status bar carries the area", app.status_bar.theme_variant == "norfair")
                app.status_bar.hud_ascii = False
                app.status_bar.set_cwd_branch("~/project", "main")
                ctx.check("the HUD shows Norfair's prefix glyph and the cwd", f"{AREAS['norfair']['glyph']} project" in _text(app.status_bar))
                await handle_slash(app, "theme", "metroid maridia")
                ctx.check("/theme metroid maridia switches the area live", app.theme_variant == "maridia" and _cfg()["theme_variant"] == "maridia")
                await handle_slash(app, "metroid", "nowhere")
                ctx.check("an unknown area is an error toast and changes nothing",
                          app.theme_variant == "maridia" and notes[-1][1] == "error" and "tourian" in notes[-1][0])
                await handle_slash(app, "metroid", "")
                ctx.check("bare /metroid still toggles off to the previous theme", app.theme_name == "claude-light")
                relaunch = _app(theme_mod.resolve_theme(env={"TERM": "xterm"}, persisted_theme="metroid"))
                ctx.check("a relaunch picks the persisted area up", relaunch.theme_variant == "maridia")
    asyncio.run(body())


@test
def test_turn_counter_and_area_field_in_a_real_bar(ctx: Ctx):
    from halo_harness import events as ev
    from halo_harness.tui.dispatch import apply_event

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                bar = app.status_bar
                bar.hud_ascii = False
                bar.set_cwd_branch("~/project", "main")
                bar.apply_status({"model": "or:demo/atlas-pro", "context_tokens": 450_000, "context_limit": 1_000_000,
                                  "cost_usd": 0.0123, "mcp": {"connected": 3, "total": 3, "tools": 41}})
                ctx.check("no turns yet: 00", "▲ 00" in _text(bar))
                await apply_event(app, ev.user_message("one", turn=1))
                await apply_event(app, ev.user_message("two", turn=2))
                ctx.check(f"two user turns: 02, got {bar.turn_count}", bar.turn_count == 2 and "▲ 02" in _text(bar))
                await apply_event(app, ev.Event("user_message", {"text": "child"}, turn=3, agent_id="sub1"))
                ctx.check("a sub-agent's message is not a turn", bar.turn_count == 2)
                plain = _text(bar)
                ctx.check("55 percent remaining shows six tanks and the number", "■■■■■■□□□□ 55%" in plain)
                ctx.check("tools loaded in SUPER", "◆ 41 tools" in plain)
                ctx.check("area panel: cwd last component and branch", "project · main" in plain)
                bar.set_error(True)
                ctx.check("the visor shows the error face", "◖x-x◗" in _text(bar))
    asyncio.run(body())


@test
def test_wizard_theme_step_offers_the_area_when_metroid_is_picked(ctx: Ctx):
    from textual.widgets import OptionList

    from halo_harness.tui.dialogs.init_wizard import InitWizardApp, WizardState

    async def body():
        with _scoped():
            theme_mod.set_config_value("theme", "claude-light")
            state = WizardState(cwd=str(Path(__file__).resolve().parent.parent), step_keys=("theme",), no_live=True)
            app = InitWizardApp(state)
            async with app.run_test(size=(110, 50)) as pilot:
                await pilot.pause(0.2)
                themes = app.screen.query_one("#wiz-theme-list", OptionList)
                areas = app.screen.query_one("#wiz-theme-variants", OptionList)
                ctx.check("the area list is hidden for a normal theme", not areas.display)
                ids = [str(themes.get_option_at_index(i).id) for i in range(themes.option_count)]
                themes.highlighted = ids.index("metroid")
                await pilot.pause(0.1)
                ctx.check("picking metroid shows the five areas", areas.display and areas.option_count == 5)
                ctx.check("the persisted/default area is highlighted", areas.highlighted == 0)
                areas.highlighted = AREA_NAMES.index("brinstar")
                await pilot.pause(0.1)
                app.screen.commit()
                ctx.check("commit persists metroid and the chosen area",
                          _cfg()["theme"] == "metroid" and _cfg()["theme_variant"] == "brinstar")
                ctx.check("... and the previous theme", _cfg()[tt.PREVIOUS_KEY] == "claude-light")
                themes.highlighted = ids.index("doom")
                await pilot.pause(0.1)
                ctx.check("picking doom hides the area list again", not areas.display)
    asyncio.run(body())


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
