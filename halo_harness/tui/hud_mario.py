"""halo_harness.tui.hud_mario -- the Mario skin: a status bar in the shape of a
platformer's top bar (score, coins, world, time, lives), drawn from scratch
(Halo 2.0.8 theme pack, round 3). Reference mood: the 8- and 16-bit era's
overworld screen. Nothing here is taken from any game.

Panel order (score, power, coins, face, world, time, lives, tools, pipes):

  SCORE   tokens left in the window (the score)
  POWER   the context meter, six blocks, the exact percent remaining
  COINS   cost, with the provider balance beside it, behind a coin glyph
  (face)  the phase face: an original cap-and-moustache ASCII face, five states
  WORLD   the cwd's last component, the branch as the "level" after it
  TIME    the clock of the current turn counting UP; idle shows the last turn
  TURNS   turns taken this session, as a lives counter
  TOOLS   tools loaded, as a second counter
  PIPES   the active providers

The bottom border is the ticker for everything else the status bar shows
(phase, mode, effort, model, full cwd, needs-you, agents, background jobs,
offline, governor, new count, throughput, the custom status line).

Two palettes share this layout as variants of the one `mario` theme: `bros`
(default) and `world`; they differ in colour and the coin glyph. `/mario
<variant>` picks one (`theme_variant` in config.json). Palettes:
`tui/theme_mario.py`.

Motifs: cards and dialogs get a brick-pattern border (`brick`, registered by
`tui/borders.py`; `ascii` without truecolor) and the input line a pipe-shaped
frame. When a sub-agent finishes or a background job completes the face slot
flashes a short "1-UP" or coin cue for about two seconds (`cues`; no sound).
"""

from __future__ import annotations

from halo_harness.tui.hud import Glyphs, HudSkin, Segment, register_skin
from halo_harness.tui.theme_mario import DEFAULT_LOOK, LOOKS

DOUBLE = Glyphs(h="═", v="║", tl="╔", tr="╗", bl="╚", br="╝", tee_down="╦", tee_up="╩",
                meter_on="█", meter_off="▒", face_l="▐", face_r="▌")
PLAIN = Glyphs(h="-", v="|", tl="+", tr="+", bl="+", br="+", tee_down="+", tee_up="+",
               meter_on="#", meter_off=".", face_l="(", face_r=")")

PANELS = (
    Segment("tokens", "SCORE", "", 10),
    Segment("context", "POWER", "", 7),
    Segment("cost", "COINS", LOOKS[DEFAULT_LOOK]["glyph"], 8),
    Segment("face", "", "", 7),
    Segment("area", "WORLD", "", 8),
    Segment("elapsed", "TIME", "", 6),
    Segment("turns", "TURNS", "♥×", 8),
    Segment("tools", "TOOLS", "★×", 8),
    Segment("providers", "PIPES", "", 7),
)

STRIP = (
    Segment("phase"), Segment("permission"), Segment("needs_you"), Segment("mode"), Segment("effort"),
    Segment("model", glyphs="▸"), Segment("agents"), Segment("bg"), Segment("offline"), Segment("gov"),
    Segment("hang"), Segment("new"), Segment("cwd", glyphs="⌂"), Segment("mcp"), Segment("throughput"),
    Segment("statusline"),
)

# The cap-and-moustache face: eyes at the sides, a moustache in the middle.
# Every frame is 5 cells wide (7 with the cap-brim glyphs around it).
FACES = {
    "idle": ("'o~o'",),
    "thinking": ("'.~o'", "'o~.'"),
    "writing": ("'^~^'", "'>~<'"),
    "error": ("'x~x'", "'X~X'"),
    "needs_you": ("'!~!'", "'O~O'"),
}

# Face-slot flashes (7 cells, plain ASCII): the 1-UP for a finished sub-agent,
# a spinning coin for a finished background job. Played for about two seconds.
CUES = {
    "agent_done": ("  1UP  ", " 1-UP! ", "1-UP!!!", " 1-UP! "),
    "job_done": ("(o) +1 ", "(0) +1 ", "(|) +1 ", "(0) +1 "),
}


def look_styles(look: str) -> dict:
    """The HUD colour roles for one palette."""
    p = LOOKS[look]["palette"]
    return {
        "border": LOOKS[look]["border"], "label": f"bold {p['bridge-accent']}", "value": p["bridge-text"],
        "glyph": p["bridge-accent"], "ok": p["bridge-success"], "warn": p["bridge-warning"],
        "bad": f"bold {p['bridge-error']}", "dim": p["bridge-muted"], "meter_off": p["bridge-thinking"],
    }


def look_face_styles(look: str) -> dict:
    p = LOOKS[look]["palette"]
    return {
        "idle": p["bridge-text"], "thinking": p["bridge-warning"], "writing": p["bridge-success"],
        "error": f"bold {p['bridge-error']}", "needs_you": f"bold {p['bridge-bg']} on {p['bridge-warning']}",
        "cue": f"bold {p['bridge-bg']} on {p['bridge-accent']}",
    }


VARIANTS = {
    name: {"styles": look_styles(name), "face_styles": look_face_styles(name), "glyphs": {"cost": look["glyph"]}}
    for name, look in LOOKS.items()
}

MARIO = HudSkin(
    name="mario",
    segments=PANELS,
    strip=STRIP,
    # first removed first; phase, context, cost, face, area, mode, needs-you,
    # permission and offline are never removed. The timer goes last of all.
    drop_order=("statusline", "throughput", "cwd", "mcp", "providers", "tools", "gov", "bg", "new", "effort",
                "turns", "model", "agents", "hang", "tokens", "elapsed"),
    faces=FACES,
    glyphs=DOUBLE,
    glyphs_ascii=PLAIN,
    styles=look_styles(DEFAULT_LOOK),
    face_styles=look_face_styles(DEFAULT_LOOK),
    heavy_borders=False,
    variants=VARIANTS,
    panel_border="brick",
    panel_border_ascii="ascii",
    input_frame=("╞", "╡"),
    input_frame_ascii=("[", "]"),
    cues=CUES,
)
register_skin(MARIO)
