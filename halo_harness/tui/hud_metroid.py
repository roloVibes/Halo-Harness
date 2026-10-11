"""halo_harness.tui.hud_metroid -- the Metroid skin: a suit-HUD status bar in
the shape of a side-scrolling shooter's heads-up display, drawn from scratch
(Halo 2.0.8 theme pack, round 2). Reference mood: the 16-bit era's visor HUD.

Panel order (energy, reserve, missiles, supers, visor, cost, beam, area):

  ENERGY   the context meter as ten energy tanks (one per ten percent of the
           context window REMAINING, filled tank = full) plus the exact number
  RESERVE  tokens left in the window (the reserve tank)
  MISSILE  turns taken this session (the missile counter)
  SUPER    tools loaded (the super-missile counter)
  (visor)  the phase face: an original visor-slit glyph set, five states
  COST     cost and the provider balance
  BEAM     the active providers
  AREA     the cwd's last component, the branch as its sub-label, behind a
           prefix glyph that names the active area variant

The bottom border is the ticker for everything else the status bar shows
(phase clock, mode, effort, model, full cwd, needs-you, agents, background
jobs, offline, governor, new count, throughput, the custom status line).

Five area variants (Crateria, Brinstar, Norfair, Maridia, Tourian) share this
layout and differ in colour and the AREA prefix glyph; `/metroid <area>`
picks one (`theme_variant` in config.json). Palettes: `tui/theme_metroid.py`.
Cards and dialogs get dashed map-grid borders (`ascii` without truecolor) and
the input line gets a visor-shaped left/right frame, both declared here and
toggled on the app like `hud-heavy`.
"""

from __future__ import annotations

from halo_harness.tui.hud import Glyphs, HudSkin, Segment, register_skin
from halo_harness.tui.theme_metroid import AREAS, DEFAULT_AREA

LIGHT = Glyphs(h="─", v="│", tl="┌", tr="┐", bl="└", br="┘", tee_down="┬", tee_up="┴",
               meter_on="■", meter_off="□", face_l="◖", face_r="◗")
PLAIN = Glyphs(h="-", v="|", tl="+", tr="+", bl="+", br="+", tee_down="+", tee_up="+",
               meter_on="#", meter_off=".", face_l="(", face_r=")")

PANELS = (
    Segment("context", "ENERGY", "", 7),
    Segment("tokens", "RESERVE", "", 10),
    Segment("turns", "MISSILE", "▲", 10),
    Segment("tools", "SUPER", "◆", 10),
    Segment("face", "", "", 7),
    Segment("cost", "COST", "", 8),
    Segment("providers", "BEAM", "", 7),
    Segment("area", "AREA", AREAS[DEFAULT_AREA]["glyph"], 8),
)

STRIP = (
    Segment("phase"), Segment("permission"), Segment("needs_you"), Segment("mode"), Segment("effort"),
    Segment("model", glyphs="▸"), Segment("agents"), Segment("bg"), Segment("offline"), Segment("gov"),
    Segment("hang"), Segment("new"), Segment("cwd", glyphs="⌂"), Segment("mcp"), Segment("throughput"),
    Segment("statusline"),
)

# The visor slit: a lit bar behind the glass. Every frame is 3 cells wide.
FACES = {
    "idle": ("-o-",),
    "thinking": ("o--", "-o-", "--o", "-o-"),
    "writing": ("<=>", ">=<"),
    "error": ("x-x", "X-X"),
    "needs_you": ("!-!", "!=!"),
}


def area_styles(area: str) -> dict:
    """The HUD colour roles for one area, from its palette."""
    p = AREAS[area]["palette"]
    return {
        "border": AREAS[area]["border"], "label": f"bold {p['bridge-accent']}", "value": p["bridge-text"],
        "glyph": p["bridge-accent"], "ok": p["bridge-success"], "warn": p["bridge-warning"],
        "bad": f"bold {p['bridge-error']}", "dim": p["bridge-muted"], "meter_off": p["bridge-thinking"],
    }


def area_face_styles(area: str) -> dict:
    p = AREAS[area]["palette"]
    return {
        "idle": p["bridge-text"], "thinking": p["bridge-warning"], "writing": p["bridge-success"],
        "error": f"bold {p['bridge-error']}", "needs_you": f"bold {p['bridge-bg']} on {p['bridge-warning']}",
    }


VARIANTS = {
    name: {"styles": area_styles(name), "face_styles": area_face_styles(name), "glyphs": {"area": area["glyph"]}}
    for name, area in AREAS.items()
}

METROID = HudSkin(
    name="metroid",
    segments=PANELS,
    strip=STRIP,
    # first removed first; phase, context, cost, face, area, mode, needs-you,
    # permission and offline are never removed.
    drop_order=("statusline", "throughput", "cwd", "mcp", "providers", "tools", "gov", "bg", "new", "effort",
                "turns", "model", "agents", "hang", "tokens"),
    faces=FACES,
    glyphs=LIGHT,
    glyphs_ascii=PLAIN,
    styles=area_styles(DEFAULT_AREA),
    face_styles=area_face_styles(DEFAULT_AREA),
    heavy_borders=False,
    meter_cells=10,
    variants=VARIANTS,
    panel_border="dashed",
    panel_border_ascii="ascii",
    input_frame=("◖", "◗"),
    input_frame_ascii=("(", ")"),
)
register_skin(METROID)
