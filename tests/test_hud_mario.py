"""tests.test_hud_mario -- the Mario skin (Halo 2.0.8 theme pack, round 3):
the declaration, the shared HUD checks (width sweep, cascade, faces, ASCII
fallback), the coins / timer / world / score / lives fields, the two palette
variants (bros, world), `/mario <variant>`, the engine's new `cues` seam and
the Textual chrome (brick border, pipe input frame, the 1-UP and coin cues,
the wizard's variant list). The toggle contract itself is pinned for all
three games in tests/test_theme_toggles.py and is NOT repeated here beyond
"bare /mario is unchanged after a variant was chosen".
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from rich.cells import cell_len

from halo_harness import theme as theme_mod
from halo_harness import theme_toggle as tt
from halo_harness.tui import hud as hud_mod
from halo_harness.tui.hud import HudField, skin_for
from halo_harness.tui.hud_render import render_hud
from halo_harness.tui.theme import variables_for
from halo_harness.tui.theme_mario import LOOKS
from tests.helpers import hud_skin_checks as chk

test, TESTS = new_registry()
VARIANT_NAMES = ("bros", "world")


@contextlib.contextmanager
def _scoped():
    saved = {k: os.environ.get(k) for k in ("BRIDGE_TEST_HOME", "BRIDGE_STATE_DIR")}
    tmp = Path(tempfile.mkdtemp(prefix="halo-mario-"))
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


# ---- the declaration -----------------------------------------------------------

@test
def test_mario_skin_is_a_declaration_on_the_shared_engine(ctx: Ctx):
    skin = skin_for("mario")
    ctx.check("mario has a skin", skin is not None and skin.name == "mario")
    chk.check_declaration(ctx, skin)
    order = [s.slot for s in skin.segments]
    ctx.check(f"panel order is score power coins face world time turns tools pipes, got {order}",
              order == ["tokens", "context", "cost", "face", "area", "elapsed", "turns", "tools", "providers"])
    labels = [s.label for s in skin.segments]
    ctx.check(f"panel captions, got {labels}",
              labels == ["SCORE", "POWER", "COINS", "", "WORLD", "TIME", "TURNS", "TOOLS", "PIPES"])
    ctx.check("six power blocks, three rows, no heavy-border class (the brick border is the chrome)",
              skin.meter_cells == 6 and skin.rows == 3 and not skin.heavy_borders)
    ctx.check("brick border, ascii without truecolor", skin.panel_border == "brick" and skin.panel_border_ascii == "ascii")
    ctx.check("pipe frame: two glyphs, two ascii fallbacks",
              len(skin.input_frame) == 2 and len(skin.input_frame_ascii) == 2
              and all(g.isascii() for g in skin.input_frame_ascii) and not any(g.isascii() for g in skin.input_frame))
    ctx.check("area is never dropped, the timer goes last of all",
              "area" not in skin.drop_order and skin.drop_order[-1] == "elapsed")
    ctx.check("mario no longer rides the placeholder accent",
              hud_mod.accent_for("mario") is None and "mario" not in hud_mod.PLACEHOLDER_ACCENTS)
    ctx.check("the skin module is a built-in", "halo_harness.tui.hud_mario" in hud_mod._BUILTIN_SKIN_MODULES)


@test
def test_shared_width_sweep_cascade_faces_and_ascii_fallback(ctx: Ctx):
    skin = skin_for("mario")
    chk.check_width_sweep(ctx, skin)
    chk.check_width_sweep(ctx, skin, ascii_mode=True)
    chk.check_cascade_follows_drop_order(ctx, skin)
    chk.check_faces(ctx, skin)
    chk.check_ascii_fallback(ctx, skin)
    for name in VARIANT_NAMES:  # a variant changes colours and a glyph, never the geometry
        v = skin_for("mario", name)
        ctx.check(f"{name}: same widths as the base skin",
                  all([cell_len(r) for r in chk.lines(v, w)] == [cell_len(r) for r in chk.lines(skin, w)]
                      for w in (46, 66, 80, 100, 140)))


@test
def test_five_faces_are_original_and_distinct_from_the_other_skins(ctx: Ctx):
    mario = skin_for("mario").faces
    others = {tuple(f) for n in ("doom", "metroid") for f in skin_for(n).faces.values()}
    ctx.check("no Mario frame set is shared with DOOM or Metroid", not ({tuple(f) for f in mario.values()} & others))
    ctx.check("the idle face wears the moustache", "~" in mario["idle"][0])
    for state, frames in mario.items():
        ctx.check(f"{state}: every frame is five cells", all(cell_len(f) == 5 for f in frames))


@test
def test_narrow_cascade_keeps_phase_context_cost_world_mode(ctx: Ctx):
    skin = skin_for("mario")
    fields = {k: v for k, v in chk.sample_fields().items() if k != "model"}
    for width in (46, 50, 66, 80):
        text = "\n".join(chk.lines(skin, width, fields=fields))
        for needle in ("62%", "$0.0123", "writing", "auto", "project"):
            ctx.check(f"{width}: {needle!r} kept", needle in text)
    ctx.check("46: the face kept", "'o~o'" in "\n".join(chk.lines(skin, 46)))
    eighty = "\n".join(chk.lines(skin, 80, fields=fields))
    for label in ("COINS", "TIME", "WORLD"):
        ctx.check(f"80 columns keeps {label}", label in eighty)
    ctx.check("80 columns keeps the timer's value", "0:23" in eighty)
    ctx.check("80 columns keeps the power blocks", "████▒▒ 62%" in eighty)
    compact = chk.lines(skin, 40)[0]
    for needle in ("62%", "$0.0123", "writing", "auto", "proj"):
        ctx.check(f"compact line keeps {needle!r}", needle in compact)
    wide = "\n".join(chk.lines(skin, 140))
    for label in ("SCORE", "POWER", "COINS", "WORLD", "TIME", "TURNS", "TOOLS", "PIPES"):
        ctx.check(f"wide shows {label}", label in wide)


# ---- the fields: coins, timer, world, score, lives --------------------------------

@test
def test_coins_timer_world_score_and_lives_fields(ctx: Ctx):
    skin = skin_for("mario")
    mid = chk.lines(skin, 160)[1]
    ctx.check("COINS carries a coin glyph, the cost and the balance beside it", "● $0.0123 · OR $12.40 left" in mid)
    ctx.check("SCORE carries tokens left", "812k left" in mid)
    ctx.check("WORLD carries the cwd's last component and the branch as the level", "project · main" in mid)
    ctx.check("TIME carries the clock", "0:23" in mid)
    ctx.check("TURNS is a lives-style counter", "♥× 07" in mid)
    ctx.check("TOOLS is a lives-style counter", "★× 41 tools" in mid)
    ctx.check("PIPES carries the providers", "or dbx" in mid)
    ctx.check("the full cwd stays reachable in the ticker", "~/project (main)" in chk.lines(skin, 160)[2])
    idle = chk.sample_fields()
    del idle["elapsed"]
    ctx.check("no turn yet: the timer shows a dash, not a gap", "-" in chk.lines(skin, 140, fields=idle)[1])
    ascii_mid = chk.lines(skin, 160, ascii_mode=True)[1]
    ctx.check("ascii mode drops the coin glyph and keeps the numbers", "$0.0123" in ascii_mid and "●" not in ascii_mid)


@test
def test_power_blocks_follow_remaining_context(ctx: Ctx):
    for frac, want in ((0.0, 0), (0.5, 3), (1.0, 6)):
        fields = chk.sample_fields()
        fields["context"] = HudField(f"{frac * 100:.0f}%", f"{frac * 100:.0f}%", "ok", frac)
        row = chk.lines(skin_for("mario"), 120, fields=fields)[1]
        ctx.check(f"{frac:.0%}: {want} full blocks of six", row.count("█") == want and row.count("▒") == 6 - want)
    ctx.check("the empty blocks are dimmed through the skin style",
              skin_for("mario").styles["meter_off"] in {str(s.style) for s in render_hud(
                  skin_for("mario"), chk.sample_fields(), width=120).spans})


@test
def test_clock_formats_are_timer_style(ctx: Ctx):
    from halo_harness.tui.hud_fields import _clock
    cases = {0: "0:00", 5: "0:05", 65: "1:05", 599: "9:59", 3600: "1:00:00", 3725: "1:02:05", -3: "0:00"}
    for secs, want in cases.items():
        ctx.check(f"{secs} s reads {want}", _clock(secs) == want)


# ---- the two variants ---------------------------------------------------------------

@test
def test_two_variants_resolve_to_distinct_palettes(ctx: Ctx):
    base_keys = set(variables_for("claude-dark"))
    palettes = {n: variables_for("mario", n) for n in VARIANT_NAMES}
    for name, pal in palettes.items():
        ctx.check(f"{name}: full variable set", set(pal) == base_keys)
    for key in ("bridge-bg", "bridge-accent", "bridge-border", "bridge-text"):
        ctx.check(f"{key} differs between bros and world", palettes["bros"][key] != palettes["world"][key])
    def dominant(hexcolor: str) -> str:
        r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
        return "rgb"[[r, g, b].index(max(r, g, b))]
    ctx.check("both keep a pipe green for success", all(dominant(p["bridge-success"]) == "g" for p in palettes.values()))
    ctx.check("the default (no variant) is bros", variables_for("mario") == palettes["bros"])
    ctx.check("an unknown variant falls back to bros", variables_for("mario", "nowhere") == palettes["bros"])
    ctx.check("a Metroid area does not leak into mario", variables_for("mario", "norfair") == palettes["bros"])
    ctx.check("a variant never leaks into another theme", variables_for("doom", "world") == variables_for("doom"))
    ctx.check("theme.GAME_VARIANTS names bros then world", theme_mod.GAME_VARIANTS["mario"] == VARIANT_NAMES
              and tuple(LOOKS) == VARIANT_NAMES)
    ctx.check("metroid's five areas are unchanged", len(theme_mod.GAME_VARIANTS["metroid"]) == 5)
    hud = {n: skin_for("mario", n) for n in VARIANT_NAMES}
    for role in ("border", "label", "glyph", "dim"):
        ctx.check(f"HUD {role} colour differs between the variants", hud["bros"].styles[role] != hud["world"].styles[role])
    ctx.check("the variants keep the cue style", all("cue" in h.face_styles for h in hud.values()))
    ctx.check("each variant has its own coin glyph", hud["bros"].segments[2].glyphs != hud["world"].segments[2].glyphs)
    ctx.check("the base skin is the bros look", skin_for("mario").styles == hud["bros"].styles)
    ctx.check("both skies lean blue, the borders lean red (bros) and orange (world)",
              dominant(palettes["bros"]["bridge-bg"]) == "b" and dominant(palettes["world"]["bridge-bg"]) == "b"
              and dominant(palettes["bros"]["bridge-border"]) == "r" and dominant(palettes["world"]["bridge-border"]) == "r")
    ctx.check("world's sky is brighter than bros'", int(palettes["world"]["bridge-bg"][5:7], 16) > int(palettes["bros"]["bridge-bg"][5:7], 16))


# ---- /mario <variant> and /theme mario <variant> ---------------------------------------

@test
def test_variant_is_persisted_by_the_toggle_helpers(ctx: Ctx):
    with _scoped():
        ctx.check("the default variant is bros", theme_mod.variant_for("mario") == "bros")
        applied = tt.set_game_variant("mario", "world", "claude-light")
        ctx.check("set_game_variant applies the game theme", applied == "mario" and _cfg()["theme"] == "mario")
        ctx.check("... remembers the previous theme", _cfg()[tt.PREVIOUS_KEY] == "claude-light")
        ctx.check("... persists theme_variant", _cfg()["theme_variant"] == "world" and theme_mod.variant_for("mario") == "world")
        tt.set_game_variant("mario", "bros", "mario")
        ctx.check("naming a variant while active re-tints without toggling off",
                  _cfg()["theme"] == "mario" and _cfg()["theme_variant"] == "bros" and _cfg()[tt.PREVIOUS_KEY] == "claude-light")
        raised = []
        for bad in ("nowhere", "", "BROS ", "norfair"):
            try:
                tt.set_game_variant("mario", bad, "claude-dark")
            except ValueError as exc:
                raised.append(str(exc))
        ctx.check("an unknown variant raises and lists bros and world",
                  len(raised) == 4 and all("bros" in r and "world" in r for r in raised))
        theme_mod.set_config_value("theme_variant", "norfair")
        ctx.check("a variant of another game falls back to bros", theme_mod.variant_for("mario") == "bros")
        ctx.check("... and metroid ignores a mario variant", (theme_mod.set_config_value("theme_variant", "world"),
                                                           theme_mod.variant_for("metroid"))[1] == "crateria")
        ctx.check("the messages call it a palette for mario, an area for metroid",
                  "palette world" in tt.variant_message("mario", "world") and "area norfair" in tt.variant_message("metroid", "norfair"))
        ctx.check("parse_theme_args splits name and variant", tt.parse_theme_args("Mario  World extra")[1:] == ("world", ["extra"]))


@test
def test_headless_variant_commands_and_the_bare_toggle_after_a_variant(ctx: Ctx):
    from halo_harness.commands.builtins import _BUILTIN_SPECS, HeadlessFacade
    run = _BUILTIN_SPECS["mario"][3]
    theme_cmd = _BUILTIN_SPECS["theme"][3]
    ctx.check("/mario advertises its [variant] argument", _BUILTIN_SPECS["mario"][2] == "[variant]")
    with _scoped():
        out = run("world", HeadlessFacade(cwd=Path("."), theme="claude-light"))
        ctx.check(f"/mario world applies it: {out!r}", "palette world" in out and _cfg()["theme"] == "mario"
                  and _cfg()["theme_variant"] == "world" and _cfg()[tt.PREVIOUS_KEY] == "claude-light")
        out = run("", HeadlessFacade(cwd=Path("."), theme="mario"))
        ctx.check(f"bare /mario still restores the previous theme: {out!r}",
                  _cfg()["theme"] == "claude-light" and tt.PREVIOUS_KEY not in _cfg())
        ctx.check("... and leaves the chosen variant alone", _cfg()["theme_variant"] == "world")
        run("", HeadlessFacade(cwd=Path("."), theme="claude-light"))
        ctx.check("bare /mario again comes back to mario with the same variant",
                  _cfg()["theme"] == "mario" and theme_mod.variant_for("mario") == "world")
        before = dict(_cfg())
        out = run("nowhere", HeadlessFacade(cwd=Path("."), theme="mario"))
        ctx.check(f"an unknown variant is reported, nothing written: {out!r}", "bros" in out and "world" in out and _cfg() == before)
        out = theme_cmd("mario bros", HeadlessFacade(cwd=Path("."), theme="claude-dark"))
        ctx.check(f"/theme mario bros: {out!r}", "palette bros" in out and _cfg()["theme"] == "mario"
                  and _cfg()["theme_variant"] == "bros")
        before = dict(_cfg())
        out = theme_cmd("mario norfair", HeadlessFacade(cwd=Path("."), theme="mario"))
        ctx.check(f"/theme mario norfair is rejected, nothing written: {out!r}", "not a mario variant" in out and _cfg() == before)
        out = theme_cmd("metroid world", HeadlessFacade(cwd=Path("."), theme="mario"))
        ctx.check(f"/theme metroid world is rejected: {out!r}", "not a metroid variant" in out and _cfg() == before)
    with _scoped():  # DOOM ignores a stray argument exactly as before
        out = _BUILTIN_SPECS["doom"][3]("world", HeadlessFacade(cwd=Path("."), theme="claude-dark"))
        ctx.check(f"/doom <anything> still toggles doom: {out!r}", _cfg()["theme"] == "doom" and "theme_variant" not in _cfg())


@test
def test_config_set_validates_mario_variants(ctx: Ctx):
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
        ctx.check("`halo config set theme_variant world` exits 0", run("world") == 0 and _cfg()["theme_variant"] == "world")
        ctx.check("bros is accepted too", run("bros") == 0 and _cfg()["theme_variant"] == "bros")
        ctx.check("a metroid area is still accepted for metroid", run("norfair") == 0)
        ctx.check("an unknown variant exits 2 and is not written", run("nowhere") == 2 and _cfg()["theme_variant"] == "norfair")


# ---- the engine's cues seam (pure part) ------------------------------------------------

@test
def test_cues_seam_is_generic_and_default_safe(ctx: Ctx):
    mario = skin_for("mario")
    ctx.check("mario declares both cues", set(mario.cues) == {"agent_done", "job_done"})
    ctx.check("doom and metroid declare none", not skin_for("doom").cues and not skin_for("metroid").cues)
    face_w = max(cell_len(skin_for("mario").glyphs.face_l + f + skin_for("mario").glyphs.face_r)
                 for frames in mario.faces.values() for f in frames)
    for event, frames in mario.cues.items():
        ctx.check(f"{event}: frames are plain ASCII and as wide as the face ({face_w})",
                  len(frames) >= 2 and all(f.isascii() and cell_len(f) == face_w for f in frames))
        ctx.check(f"{event}: frames differ (it animates)", len(set(frames)) > 1)
    ctx.check("the 1-UP cue reads 1UP, the coin cue shows a coin", all("1" in f and "UP" in f for f in mario.cues["agent_done"])
              and any("o" in f for f in mario.cues["job_done"]))
    for state in ("idle", "writing"):
        plain = render_hud(mario, chk.sample_fields(), width=100, face_state=state, cue="1-UP!!!").plain
        ctx.check(f"{state}: a cue frame replaces the face in the middle row, every row still full width",
                  "1-UP!!!" in plain.split("\n")[1] and mario.faces[state][0] not in plain
                  and all(cell_len(r) == 100 for r in plain.split("\n")))
    compact = render_hud(mario, chk.sample_fields(), width=40, cue="1-UP!!!").plain
    ctx.check("the compact line shows the cue too", compact.startswith("1-UP!!!") and cell_len(compact) <= 40)
    ctx.check("an empty cue leaves the face alone", mario.faces["idle"][0] in render_hud(mario, chk.sample_fields(), width=100).plain)
    cue_style = render_hud(mario, chk.sample_fields(), width=100, cue="1-UP!!!").spans
    ctx.check("the cue is drawn in the skin's cue style", mario.face_styles["cue"] in {str(s.style) for s in cue_style})
    from halo_harness.tui.hud import Glyphs, HudSkin, Segment
    g = Glyphs(h="-", v="|", tl="+", tr="+", bl="+", br="+", tee_down="+", tee_up="+", meter_on="#", meter_off=".")
    tiny = HudSkin("x", (Segment("face", "", "", 7),), (), (), {"idle": ("o",)}, g, g, {}, cues={"e": ("WIDE-CUE-HERE",)})
    row = render_hud(tiny, {}, width=60).plain.split("\n")[1]
    ctx.check("a cue wider than the faces still widens the face slot, no clipping", row.count("|") >= 2 and cell_len(row) == 60)


# ---- inside a real app: chrome classes, pipe frame, live variant switch -----------------

def _app(theme: str = "mario"):
    from halo_harness.testing.fake_controller import FakeController
    from halo_harness.tui.app import BridgeApp
    return BridgeApp(FakeController(), cwd="~/project", theme_name=theme)


def _text(widget) -> str:
    return str(widget.render())


@test
def test_brick_type_is_registered_and_renders(ctx: Ctx):
    from textual._border import BORDER_CHARS
    from textual.css.constants import VALID_BORDER

    from halo_harness.tui import borders
    ctx.check("the brick border type registered against the pinned Textual", borders.BRICK_READY)
    ctx.check("... in the char table and the validator", "brick" in BORDER_CHARS and "brick" in VALID_BORDER)
    ctx.check("the chars are a medium-shade wall", set("".join("".join(r) for r in BORDER_CHARS["brick"])) == {"▒", " "})
    ctx.check("registering twice is harmless", borders.register_border_types())

    async def body():
        with _scoped():
            app = _app()
            async with app.run_test(size=(110, 30)) as pilot:
                await pilot.pause(0.1)
                ctx.check("the app loaded the brick stylesheet", any("styles_brick" in str(p) for p in app.css_path))
                from textual.widgets import Static
                app.status_bar.hud_ascii = False  # a truecolor terminal
                app._sync_theme_chrome()
                probe = Static("x", classes="permission-card")
                await app.mount(probe)
                await pilot.pause(0.1)
                ctx.check(f"a card under mario draws a brick border, got {probe.styles.border_top[0]!r}",
                          probe.styles.border_top[0] == "brick")
    asyncio.run(body())


@test
def test_brick_border_and_pipe_frame_follow_the_skin(ctx: Ctx):
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
                ctx.check(f"3 rows under mario, got {bar.size.height}", bar.size.height == 3)
                ctx.check("brick class on the app", app.has_class("hud-border-brick") and not app.has_class("hud-border-ascii"))
                ctx.check("no heavy class (that is DOOM's)", not app.has_class("hud-heavy"))
                ctx.check("the framed-input class is on the app", app.has_class("hud-visor"))
                ctx.check(f"left pipe glyph, got {_text(glyph)!r}", "╞" in _text(glyph))
                ctx.check(f"right pipe glyph, got {_text(right)!r}", "╡" in _text(right) and right.display)
                bar.hud_ascii = True
                app._sync_theme_chrome()
                await pilot.pause(0.05)
                ctx.check("no truecolor: ascii border class replaces brick", app.has_class("hud-border-ascii") and not app.has_class("hud-border-brick"))
                ctx.check("no truecolor: ascii pipe", "[" in _text(glyph) and "]" in _text(right) and "╞" not in _text(glyph))
                bar.hud_ascii = False
                app.apply_theme("metroid")
                await pilot.pause(0.1)
                ctx.check("metroid: dashed map border, no brick", app.has_class("hud-border-dashed") and not app.has_class("hud-border-brick"))
                app.apply_theme("doom")
                await pilot.pause(0.1)
                ctx.check("doom: no brick or pipe classes, heavy back",
                          not any(c.startswith("hud-border-") for c in app.classes) and not app.has_class("hud-visor")
                          and app.has_class("hud-heavy"))
                app.apply_theme("claude-dark")
                await pilot.pause(0.1)
                ctx.check("a normal theme carries none of the game classes",
                          not app.has_class("hud-heavy") and not app.has_class("hud-visor")
                          and not any(c.startswith("hud-border-") for c in app.classes) and "❯" in _text(glyph))
    asyncio.run(body())


@test
def test_live_variant_switch_recolours_the_app_and_the_hud(ctx: Ctx):
    from halo_harness.tui.slash import handle_slash

    async def body():
        with _scoped():
            app = _app("claude-light")
            notes = []
            app.notify = lambda msg, **kw: notes.append((msg, kw.get("severity")))
            async with app.run_test(size=(110, 30)) as pilot:
                await pilot.pause(0.05)
                await handle_slash(app, "mario", "world")
                await pilot.pause(0.1)
                ctx.check(f"/mario world: theme and variant, got {app.theme_name!r}/{app.theme_variant!r}",
                          app.theme_name == "mario" and app.theme_variant == "world")
                ctx.check("the stylesheet variables are world's", app.get_css_variables()["bridge-bg"] == LOOKS["world"]["palette"]["bridge-bg"])
                ctx.check("the status bar carries the variant", app.status_bar.theme_variant == "world")
                app.status_bar.hud_ascii = False
                app.status_bar.set_cwd_branch("~/project", "main")
                ctx.check("the HUD shows world's coin glyph", f"{LOOKS['world']['glyph']} " in _text(app.status_bar))
                await handle_slash(app, "mario", "bros")
                ctx.check("/mario bros switches back live", app.theme_variant == "bros"
                          and app.get_css_variables()["bridge-bg"] == LOOKS["bros"]["palette"]["bridge-bg"])
                await handle_slash(app, "theme", "mario world")
                ctx.check("/theme mario world switches live", app.theme_variant == "world" and _cfg()["theme_variant"] == "world")
                await handle_slash(app, "mario", "nowhere")
                ctx.check("an unknown variant is an error toast and changes nothing",
                          app.theme_variant == "world" and notes[-1][1] == "error" and "bros" in notes[-1][0])
                await handle_slash(app, "mario", "")
                ctx.check("bare /mario still toggles off to the previous theme", app.theme_name == "claude-light")
                relaunch = _app(theme_mod.resolve_theme(env={"TERM": "xterm"}, persisted_theme="mario"))
                ctx.check("a relaunch picks the persisted variant up", relaunch.theme_variant == "world")
    asyncio.run(body())


@test
def test_timer_counts_up_while_a_turn_runs_and_idle_shows_the_last_turn(ctx: Ctx):
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
                ctx.check("no turn yet: the TIME panel shows a dash", "TIME" in _text(bar) and "0:" not in _text(bar))
                await apply_event(app, ev.user_message("go", turn=1))
                bar.start_phase_clock("thinking")
                bar._turn_started_at = time.monotonic() - 65
                bar._phase_started_at = time.monotonic() - 3  # the per-call clock restarts; the TIME clock must not
                bar._refresh_display()
                ctx.check(f"a running turn: the clock reads 1:0x, got {_text(bar)!r}", "1:05" in _text(bar) or "1:06" in _text(bar))
                bar._turn_started_at = time.monotonic() - 125
                bar._refresh_display()
                ctx.check("... and keeps counting up", "2:05" in _text(bar) or "2:06" in _text(bar))
                await apply_event(app, ev.turn_done(turn=1))
                ctx.check(f"idle: the last turn's time stays, got {bar.last_turn_s}", bar.last_turn_s and 124 < bar.last_turn_s < 130)
                first = _text(bar)
                ctx.check("... shown in the TIME panel", "2:05" in first or "2:06" in first)
                time.sleep(1.1)
                bar._refresh_display()
                ctx.check("idle time does not tick on", _text(bar) == first)
                await apply_event(app, ev.Event("turn_done", {"reason": "end_turn"}, turn=2, agent_id="sub1"))
                ctx.check("a sub-agent's turn_done does not overwrite it", bar.last_turn_s and bar.last_turn_s > 100)
    asyncio.run(body())


@test
def test_wizard_theme_step_offers_the_two_variants_when_mario_is_picked(ctx: Ctx):
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
                variants = app.screen.query_one("#wiz-theme-variants", OptionList)
                ids = [str(themes.get_option_at_index(i).id) for i in range(themes.option_count)]
                themes.highlighted = ids.index("mario")
                await pilot.pause(0.1)
                shown = [str(variants.get_option_at_index(i).id) for i in range(variants.option_count)]
                ctx.check(f"picking mario shows bros and world, got {shown}", variants.display and shown == list(VARIANT_NAMES))
                ctx.check("the default variant is highlighted", variants.highlighted == 0)
                variants.highlighted = 1
                await pilot.pause(0.1)
                app.screen.commit()
                ctx.check("commit persists mario and world", _cfg()["theme"] == "mario" and _cfg()["theme_variant"] == "world")
                ctx.check("... and the previous theme", _cfg()[tt.PREVIOUS_KEY] == "claude-light")
                themes.highlighted = ids.index("metroid")
                await pilot.pause(0.1)
                ctx.check("switching to metroid refills the list with its five areas", variants.option_count == 5)
                themes.highlighted = ids.index("doom")
                await pilot.pause(0.1)
                ctx.check("picking doom hides the variant list", not variants.display)
    asyncio.run(body())


# ---- the 1-UP and coin cues in a real bar ---------------------------------------------------

@contextlib.contextmanager
def _fast_cues(seconds: float = 0.5, step: float = 0.05):
    from halo_harness.tui.widgets import statusbar as sb
    saved = sb.CUE_SECONDS, sb.CUE_STEP
    sb.CUE_SECONDS, sb.CUE_STEP = seconds, step
    try:
        yield sb
    finally:
        sb.CUE_SECONDS, sb.CUE_STEP = saved


def _fixture(bar) -> None:
    bar.hud_ascii = False
    bar.set_cwd_branch("~/project", "main")
    bar.apply_status({"model": "or:demo/atlas-pro", "context_tokens": 450_000, "context_limit": 1_000_000,
                      "cost_usd": 0.0123, "mcp": {"connected": 3, "total": 3, "tools": 41}})


@test
def test_cue_timing_constants_are_about_two_seconds(ctx: Ctx):
    from halo_harness.tui.widgets import statusbar as sb
    ctx.check("a cue lasts about two seconds", 1.5 <= sb.CUE_SECONDS <= 2.5)
    ctx.check("... in frames well under a second each", 0.1 <= sb.CUE_STEP <= 0.5)


@test
def test_one_up_cue_shows_and_clears_on_a_timer(ctx: Ctx):
    async def body():
        with _scoped(), _fast_cues(0.5, 0.05):
            app = _app()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                bar = app.status_bar
                _fixture(bar)
                bar._refresh_display()
                idle_face = skin_for("mario").glyphs.face_l + skin_for("mario").faces["idle"][0] + skin_for("mario").glyphs.face_r
                ctx.check("before: the idle face is showing, no cue", idle_face in _text(bar) and bar.cue_active() is None)
                ctx.check("fire_cue reports it started", bar.fire_cue("agent_done") is True)
                ctx.check("the cue is active", bar.cue_active() == "agent_done")
                ctx.check(f"the 1-UP is in the face slot, got {_text(bar)!r}", "1UP" in _text(bar) or "1-UP" in _text(bar))
                ctx.check("... and the idle face is gone", idle_face not in _text(bar))
                seen = set()
                for _ in range(8):
                    await pilot.pause(0.05)
                    seen.add(_text(bar).split("\n")[1])
                ctx.check("the flash animates while it plays", len(seen) > 1 or bar.cue_active() is None)
                await pilot.pause(0.5)
                ctx.check("the cue cleared itself", bar.cue_active() is None and bar._cue_timer is None)
                ctx.check("the face is back", idle_face in _text(bar) and "UP" not in _text(bar))
                bar.fire_cue("agent_done")
                bar.fire_cue("job_done")
                ctx.check("a second cue replaces the first", bar.cue_active() == "job_done")
                ctx.check("... as a coin", "+1" in _text(bar))
                bar.set_theme("doom", None)
                ctx.check("changing theme ends a cue at once", bar.cue_active() is None and bar._cue_timer is None)
                ctx.check("an event the skin has no cue for is ignored", bar.fire_cue("nothing") is False)
    asyncio.run(body())


@test
def test_cue_in_ascii_mode_stays_ascii(ctx: Ctx):
    async def body():
        with _scoped(), _fast_cues(0.4, 0.05):
            app = _app()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                bar = app.status_bar
                _fixture(bar)
                bar.hud_ascii = True
                bar.fire_cue("job_done")
                ctx.check("an ascii cue frame sits in an ascii panel row", "(o) +1" in _text(bar) and _text(bar).split("\n")[0].isascii())
                await pilot.pause(0.6)
    asyncio.run(body())


@test
def test_dispatch_triggers_the_cues(ctx: Ctx):
    from halo_harness import events as ev
    from halo_harness.tui.dispatch import apply_event

    async def body():
        with _scoped(), _fast_cues(0.5, 0.05):
            app = _app()
            async with app.run_test(size=(120, 30)) as pilot:
                await pilot.pause(0.1)
                bar = app.status_bar
                _fixture(bar)
                await apply_event(app, ev.Event("subagent_start", {"name": "scout", "agent_id": "c1"}, turn=1, agent_id="c1"))
                ctx.check("a sub-agent starting is not a cue", bar.cue_active() is None)
                await apply_event(app, ev.Event("subagent_end", {"name": "scout", "agent_id": "c1"}, turn=1, agent_id="c1"))
                ctx.check("a finished sub-agent flashes the 1-UP", bar.cue_active() == "agent_done" and "UP" in _text(bar))
                await pilot.pause(0.7)
                ctx.check("... and it clears", bar.cue_active() is None)
                await apply_event(app, ev.status_notice("background job 'suite' finished", turn=2))
                ctx.check("a delivered job-completion notice flashes the coin", bar.cue_active() == "job_done" and "+1" in _text(bar))
                await pilot.pause(0.7)
                bar.set_background_activity(bg_jobs=2, oldest_elapsed_s=5.0)
                ctx.check("jobs starting or running is not a cue", bar.cue_active() is None)
                bar.set_background_activity(bg_jobs=1, oldest_elapsed_s=6.0)
                ctx.check("the polled job count dropping (a job completed) flashes the coin", bar.cue_active() == "job_done")
                bar.set_background_activity(bg_jobs=0, oldest_elapsed_s=None)  # the app's own 1 s poll reports the real 0
                for _ in range(40):  # let every cue play out
                    await pilot.pause(0.1)
                    if bar.cue_active() is None and bar._prev_bg_jobs == 0:
                        break
                bar.set_background_activity(bg_jobs=0, oldest_elapsed_s=None)
                ctx.check("a steady count does not re-fire it", bar.cue_active() is None)
    asyncio.run(body())


@test
def test_cues_are_a_noop_for_doom_metroid_and_the_default_bar(ctx: Ctx):
    from halo_harness import events as ev
    from halo_harness.tui.dispatch import apply_event

    async def body():
        for theme in ("doom", "metroid", "claude-dark"):
            with _scoped(), _fast_cues(0.5, 0.05):
                app = _app(theme)
                async with app.run_test(size=(120, 30)) as pilot:
                    await pilot.pause(0.1)
                    bar = app.status_bar
                    _fixture(bar)
                    bar._refresh_display()
                    ctx.check(f"{theme}: fire_cue returns False", bar.fire_cue("agent_done") is False and bar.fire_cue("job_done") is False)
                    ctx.check(f"{theme}: no timer started, no cue state", bar._cue is None and bar._cue_timer is None)
                    await apply_event(app, ev.Event("subagent_end", {"name": "scout", "agent_id": "c1"}, turn=1, agent_id="c1"))
                    await apply_event(app, ev.status_notice("job finished", turn=2))
                    bar.set_background_activity(bg_jobs=2, oldest_elapsed_s=1.0)
                    bar.set_background_activity(bg_jobs=0, oldest_elapsed_s=None)
                    ctx.check(f"{theme}: the bar is unchanged by the events", bar.cue_active() is None
                              and "1UP" not in _text(bar) and "+1" not in _text(bar))
    asyncio.run(body())


@test
def test_mario_skin_files_use_only_original_art_and_no_sound(ctx: Ctx):
    root = Path(__file__).resolve().parent.parent / "halo_harness" / "tui"
    text = "\n".join((root / n).read_text(encoding="utf-8") for n in ("hud_mario.py", "theme_mario.py", "borders.py"))
    ctx.check("no sound is played anywhere in the Mario skin", not any(w in text.lower() for w in ("bell", "beep", "playsound", "\\a")))
    ctx.check("no copied strings: the skin names no game title or character", not any(
        w in text.lower() for w in ("nintendo", "luigi", "bowser", "goomba", "koopa", "peach")))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
