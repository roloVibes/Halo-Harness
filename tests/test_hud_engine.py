"""tests.test_hud_engine -- the game-HUD status-bar engine (Halo 2.0.8 theme
pack, round 1): the skin declaration, the DOOM skin, the renderer's width
cascade, the face states, the ASCII fallback, the slot vocabulary and the
StatusBar wiring. Pure tests first, Textual pilots last.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.helpers.provider_env_defaults import ensure_default_provider_credentials, ensure_scoped_state_dir_once
from tests.helpers.runner import Ctx, new_registry, print_results, run_all

ensure_default_provider_credentials()
ensure_scoped_state_dir_once()

from rich.cells import cell_len

from halo_harness.tui import hud as hud_mod
from halo_harness.tui.hud import FACE_STATES, SLOTS, HudField, face_state_for, skin_for
from halo_harness.tui.hud_render import render_hud

test, TESTS = new_registry()


def _fields() -> dict:
    return {
        "model": HudField("or:demo/atlas-pro", "atlas-pro"),
        "tokens": HudField("812k left", "812k", "ok"),
        "context": HudField("62%", "62%", "ok", 0.62),
        "tools": HudField("41 tools", "41", "ok"),
        "mcp": HudField("MCP 3/3", "3/3", "ok"),
        "cost": HudField("$0.0123 · OR $12.40 left", "$0.0123"),
        "providers": HudField("or dbx", "or", "ok"),
        "cwd": HudField("~/project (main)", "project (main)", "dim"),
        "mode": HudField("auto", "auto"),
        "effort": HudField("high"),
        "agents": HudField("agents 2"),
        "phase": HudField("⠋ writing 23 s · ↓1.2k", "⠋ writing", "warn"),
    }


def _lines(width: int, state: str = "idle", ascii_mode: bool = False, fields=None) -> list:
    text = render_hud(skin_for("doom"), fields if fields is not None else _fields(), width=width,
                      face_state=state, ascii_mode=ascii_mode)
    return text.plain.split("\n")


# ---- the declaration ------------------------------------------------------

@test
def test_doom_skin_is_a_pure_declaration_over_the_slot_vocabulary(ctx: Ctx):
    skin = skin_for("doom")
    ctx.check("doom has a skin", skin is not None)
    named = [s.slot for s in skin.segments] + [s.slot for s in skin.strip] + list(skin.compact) + list(skin.drop_order)
    unknown = sorted({n for n in named if n not in SLOTS})
    ctx.check(f"every slot a skin names is in the shared vocabulary, unknown: {unknown}", not unknown)
    order = [s.slot for s in skin.segments]
    ctx.check(f"panel order is ammo, health, arms, face, armor, keys, got {order}",
              order == ["tokens", "context", "tools", "face", "cost", "providers"])
    labels = [s.label for s in skin.segments]
    ctx.check(f"panel captions are AMMO HEALTH ARMS (face) ARMOR KEYS, got {labels}",
              labels == ["AMMO", "HEALTH", "ARMS", "", "ARMOR", "KEYS"])
    keep = {"phase", "context", "cost", "cwd", "mode", "face", "needs_you", "permission", "offline"}
    ctx.check("the narrow-cascade keepers are never in drop_order", not (keep & set(skin.drop_order)))
    ctx.check("heavy borders requested", skin.heavy_borders and skin.rows == 3)


@test
def test_only_game_themes_with_a_skin_use_the_engine(ctx: Ctx):
    for name in ("claude-dark", "claude-light-ansi", "", None, "not-a-theme"):
        ctx.check(f"{name!r} renders through the default layout", skin_for(name) is None)
    ctx.check("metroid has a skin since round 2, mario since round 3",
              skin_for("metroid") is not None and skin_for("mario") is not None)
    ctx.check("no game theme needs a placeholder accent any more",
              hud_mod.PLACEHOLDER_ACCENTS == {} and all(hud_mod.accent_for(n) is None for n in ("doom", "metroid", "mario")))
    hud_mod.PLACEHOLDER_ACCENTS["future-theme"] = "#123456"  # the mechanism stays for any future theme
    try:
        ctx.check("the placeholder mechanism still tints a theme without a skin",
                  hud_mod.accent_for("future-theme") == "#123456" and skin_for("future-theme") is None)
    finally:
        hud_mod.PLACEHOLDER_ACCENTS.pop("future-theme", None)


@test
def test_faces_cover_all_five_states_and_stay_original_ascii(ctx: Ctx):
    skin = skin_for("doom")
    ctx.check("five states declared", set(skin.faces) == set(FACE_STATES) and len(FACE_STATES) == 5)
    seen = set()
    for state, frames in skin.faces.items():
        ctx.check(f"{state}: frames are non-empty ASCII", frames and all(f.isascii() and f.strip() for f in frames))
        seen.add(frames)
    ctx.check("every state has its own distinct face", len(seen) == 5)
    widths = {cell_len(f) for frames in skin.faces.values() for f in frames}
    ctx.check(f"all frames are the same width, got {widths}", len(widths) == 1)


@test
def test_face_state_priority(ctx: Ctx):
    cases = [
        (("idle", False, False), "idle"), (("thinking", False, False), "thinking"),
        (("waiting", False, False), "thinking"), (("compacting", False, False), "thinking"),
        (("writing", False, False), "writing"), (("tool", False, False), "writing"),
        (("running", False, False), "writing"),
        (("idle", True, False), "error"), (("writing", True, False), "error"),
        (("writing", True, True), "needs_you"), (("idle", False, True), "needs_you"),
    ]
    for (phase, err, needs), want in cases:
        got = face_state_for(phase, error=err, needs_you=needs)
        ctx.check(f"{phase}/error={err}/needs_you={needs} -> {want}, got {got}", got == want)


# ---- rendering: every width, three tiers, compact ---------------------------

@test
def test_every_width_from_compact_to_wide_is_exactly_the_terminal_width(ctx: Ctx):
    bad = []
    for width in range(46, 221):
        lines = _lines(width)
        if len(lines) != 3 or any(cell_len(line) != width for line in lines):
            bad.append((width, [cell_len(line) for line in lines]))
    ctx.check(f"3 rows of exactly `width` cells for 46..220 columns, bad: {bad[:3]}", not bad)
    bad = []
    for width in range(20, 46):
        lines = _lines(width)
        if len(lines) != 1 or cell_len(lines[0]) > width:
            bad.append(width)
    ctx.check(f"1 compact row that fits for 20..45 columns, bad: {bad[:3]}", not bad)


@test
def test_width_cascade_wide_medium_narrow(ctx: Ctx):
    wide, medium, narrow = "\n".join(_lines(140)), "\n".join(_lines(66)), "\n".join(_lines(50))
    for label in ("AMMO", "HEALTH", "ARMS", "ARMOR", "KEYS"):
        ctx.check(f"wide shows {label}", label in wide)
    ctx.check("wide shows the balance next to cost", "OR $12.40 left" in wide)
    ctx.check("wide shows the full model ref", "or:demo/atlas-pro" in wide)
    ctx.check("medium drops KEYS but keeps AMMO HEALTH ARMS ARMOR",
              "KEYS" not in medium and all(w in medium for w in ("AMMO", "HEALTH", "ARMS", "ARMOR")))
    ctx.check("narrow drops ARMS but keeps AMMO HEALTH ARMOR and the face",
              "ARMS" not in narrow and all(w in narrow for w in ("AMMO", "HEALTH", "ARMOR")) and "o_o" in narrow)
    tiny = "\n".join(_lines(46))
    ctx.check("at 46 ARMS and KEYS are gone, HEALTH and ARMOR remain beside the face",
              "HEALTH" in tiny and "ARMOR" in tiny and "ARMS" not in tiny and "KEYS" not in tiny)


@test
def test_dropped_slots_only_grow_as_the_terminal_narrows(ctx: Ctx):
    from halo_harness.tui.hud_render import cascade
    skin = skin_for("doom")
    previous: set = set()
    for width in range(200, 45, -1):
        panels, strip, _forms = cascade(skin, _fields(), width, False)
        shown = {s.slot for s in panels} | {s.slot for s in strip}
        offered = {s.slot for s in skin.segments} | {s.slot for s in skin.strip if s.slot in _fields()}
        dropped = offered - shown
        ctx.check(f"width {width}: nothing dropped earlier comes back", previous <= dropped)
        previous = dropped
    # the dropped set at any width is a prefix of the declared drop order (among slots on offer)
    on_offer = {x.slot for x in skin.segments} | set(_fields())
    order = [x for x in skin.drop_order if x in on_offer]
    for width in range(46, 200):
        panels, strip, _f = cascade(skin, _fields(), width, False)
        shown = {x.slot for x in panels} | {x.slot for x in strip}
        dropped = {x.slot for x in skin.segments + skin.strip if x.slot in on_offer} - shown
        k = len(dropped)
        ctx.check(f"width {width}: dropped {sorted(dropped)} is the first {k} of the declared order",
                  dropped == set(order[:k]))


@test
def test_narrowest_cascade_keeps_phase_context_cost_cwd_mode(ctx: Ctx):
    for width in (46, 50):
        text = "\n".join(_lines(width, fields={k: v for k, v in _fields().items() if k != "model"}))
        ctx.check(f"{width}: context percent kept", "62%" in text)
        ctx.check(f"{width}: cost kept", "$0.0123" in text)
        ctx.check(f"{width}: phase kept", "writing" in text)
        ctx.check(f"{width}: mode kept", "auto" in text)
        ctx.check(f"{width}: the face kept", "^o^" in text.replace("▐", "[").replace("▌", "]") or "(" in text)
    text = "\n".join(_lines(46, fields={k: v for k, v in _fields().items() if k not in ("model", "effort")}))
    ctx.check("46: cwd kept (at least its first characters)", "⌂" in text)
    compact = _lines(40)[0]
    for needle in ("62%", "$0.0123", "writing", "auto"):
        ctx.check(f"compact line keeps {needle!r}: {compact!r}", needle in compact)


@test
def test_each_face_state_renders_its_own_face(ctx: Ctx):
    skin = skin_for("doom")
    for state in FACE_STATES:
        mid = _lines(100, state)[1]
        face = skin.faces[state][0]
        ctx.check(f"{state}: the face {face!r} is in the middle row", face in mid)
    frame1 = render_hud(skin, _fields(), width=100, face_state="writing", frame=1).plain.split("\n")[1]
    ctx.check("the writing face animates with the spinner tick", skin.faces["writing"][1] in frame1)


@test
def test_ascii_mode_uses_ascii_box_glyphs(ctx: Ctx):
    ascii_fields = {k: HudField(v.long.encode("ascii", "ignore").decode(), v.short.encode("ascii", "ignore").decode(),
                                v.tone, v.frac) for k, v in _fields().items()}
    for width in (60, 80, 120):
        lines = _lines(width, "needs_you", ascii_mode=True, fields=ascii_fields)
        text = "\n".join(lines)
        ctx.check(f"{width}: every character is ASCII in ascii mode", text.isascii())
        ctx.check(f"{width}: ascii borders are + - |", lines[0][0] == "+" and lines[1][0] == "|")
        ctx.check(f"{width}: still full width", all(cell_len(line) == width for line in lines))
    ctx.check("unicode mode uses the heavy glyphs", _lines(80)[0][0] == "┏" and _lines(80)[1][0] == "┃")


@test
def test_missing_fields_do_not_break_the_row(ctx: Ctx):
    lines = _lines(100, fields={"cost": HudField("$0.0000", "$0.0000"), "mode": HudField("auto", "auto"),
                                "context": HudField("--%", "", "dim")})
    ctx.check("three rows", len(lines) == 3)
    ctx.check("every cell is full width", all(cell_len(line) == 100 for line in lines))
    ctx.check("missing panels show a dash, not a gap", "-" in lines[1])


@test
def test_palettes_have_the_full_key_set_for_all_three(ctx: Ctx):
    from halo_harness.tui.theme import variables_for
    base = set(variables_for("claude-dark"))
    for name in ("doom", "metroid", "mario"):
        v = variables_for(name)
        ctx.check(f"{name}: same variable names as the base palette", set(v) == base)
        ctx.check(f"{name}: differs from claude-dark", v != variables_for("claude-dark"))
    ctx.check("doom text is amber", variables_for("doom")["bridge-text"].lower().startswith("#d"))


if __name__ == "__main__":
    ctx = Ctx()
    results, passed, failed, skipped = run_all(TESTS, ctx)
    sys.exit(print_results(results, passed, failed, skipped))
