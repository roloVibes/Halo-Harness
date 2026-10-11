"""halo_harness.tui.hud_doom -- the DOOM skin: a bottom-HUD status bar in the
shape of a classic shooter's heads-up display, drawn from scratch.

Panel order (ammo, health, arms, face, armor, keys) carries, in turn:
tokens remaining, context remaining percent, tools loaded, the phase face,
cost or balance, providers. The bottom border line is the ticker for
everything else the status bar shows (phase clock, mode, effort, model,
cwd and branch, needs-you, agents, background jobs, offline, governor,
new count, throughput, the custom status line).

The face is an original ASCII "guy" with a helmet; it is NOT taken from
any game. Palette: `tui/theme_games.py::DOOM`.
"""

from __future__ import annotations

from halo_harness.tui.hud import Glyphs, HudSkin, Segment, register_skin

HEAVY = Glyphs(h="━", v="┃", tl="┏", tr="┓", bl="┗", br="┛", tee_down="┳", tee_up="┻",
               meter_on="█", meter_off="░", face_l="▐", face_r="▌")
PLAIN = Glyphs(h="-", v="|", tl="+", tr="+", bl="+", br="+", tee_down="+", tee_up="+",
               meter_on="#", meter_off="-", meter_l="[", meter_r="]", face_l="[", face_r="]")

PANELS = (
    Segment("tokens", "AMMO", "◆", 7),
    Segment("context", "HEALTH", "", 7),
    Segment("tools", "ARMS", "▲", 7),
    Segment("face", "", "", 7),
    Segment("cost", "ARMOR", "", 8),
    Segment("providers", "KEYS", "", 7),
)

STRIP = (
    Segment("phase"), Segment("permission"), Segment("needs_you"), Segment("mode"), Segment("effort"),
    Segment("model", glyphs="▸"), Segment("agents"), Segment("bg"), Segment("offline"), Segment("gov"),
    Segment("hang"), Segment("new"), Segment("cwd", glyphs="⌂"), Segment("mcp"), Segment("throughput"),
    Segment("statusline"),
)

FACES = {
    "idle": ("o_o",),
    "thinking": ("'_'", "'.'"),
    "writing": ("^o^", "^_^"),
    "error": ("x_x", "X_X"),
    "needs_you": ("O!O", "o!o"),
}

DOOM = HudSkin(
    name="doom",
    segments=PANELS,
    strip=STRIP,
    # first removed first; phase, context, cost, face, cwd, mode, needs-you,
    # permission and offline are never removed.
    drop_order=("statusline", "throughput", "mcp", "providers", "gov", "bg", "new", "effort", "model",
                "agents", "hang", "tools", "tokens"),
    faces=FACES,
    glyphs=HEAVY,
    glyphs_ascii=PLAIN,
    styles={
        "border": "#7a3b22", "label": "bold #c8372d", "value": "#d9a441", "glyph": "#c9773b",
        "ok": "#7f9a4b", "warn": "#e8b04a", "bad": "bold #ff5a45", "dim": "#8a7357",
    },
    face_styles={
        "idle": "#d9a441", "thinking": "#e8b04a", "writing": "#7f9a4b", "error": "bold #ff5a45",
        "needs_you": "bold #12100e on #e8b04a",
    },
)
register_skin(DOOM)
