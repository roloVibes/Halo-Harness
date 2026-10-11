"""halo_harness.tui.scene_doom -- the DOOM theme's level (Halo 2.0.11
round A3): a marine in green armour with a shotgun walking a tech base of
steel pillars, barrels and a sealed door; an imp stalks in from the right
while the model thinks and lands a fireball when a turn errors; the
shotgun flashes while the model writes; a fallen imp when a sub-agent
finishes, a health bonus when a job completes. Original art in the spirit
of the 1993 sprites; nothing here is copied from any game.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Scene, register_scene

COLORS = {
    "G": "#5fa84f", "D": "#2f6f2a", "S": "#e0b080", "W": "#b0b0b0", "K": "#1c1c1c",
    "B": "#9b5b2a", "R": "#ff4040", "F": "#ff8c1a", "Y": "#ffe14d",
    "T": "#6a6a72", "L": "#9ea0a8", "M": "#3c3c44", "E": "#3f8f3f", "X": "#c0392b", "U": "#7a5230",
    "P": "#4080ff",
}

HERO = {
    "idle": ((".GGG.", ".SSK.", "GGGWW", ".DD..", ".G.G."),),
    "writing": ((".GGG.", ".SSK.", "GGGWW.", ".DD..", "G...G"),
                (".GGG.", ".SSK.", "GGGWWY", ".DD..", ".GG..")),
    "thinking": ((".GGG.", ".SSK.", "GGGWW", ".DD..", ".G.G."),
                 (".GGG.", ".KSS.", "GGGWW", ".DD..", ".G.G.")),
    "error": ((".GGG.", ".RRK.", "RRRWW", ".DD..", ".G.G."),),
    "needs_you": ((".GGG.", ".SSK.", "GGGWW", ".DD..", ".G.G."),
                  ("YGGGY", ".SSK.", "GGGWW", ".DD..", ".G.G.")),
}

IMP = Mover(frames=((".B.B.", "BRBRB", ".BBB.", "B.B.B"),
                    (".B.B.", "BRBRB", "FBBBB", "B.B.B")),
            phases=frozenset({"thinking"}), speed=1, y=0)

PILLAR = ("TLT", "TMT", "TLT", "TMT")
BARREL = ("EEE", "EXE", "EEE")
DOOR = ("UUUU", "ULLU", "ULLU", "UUUU")
LAMP = ("Y", "T")

LAYERS = (
    Layer(sprites=(LAMP,), spacing=29, speed=1.0, y=4),
    Layer(sprites=(DOOR,), spacing=101, speed=1.0, y=0),
    Layer(sprites=(PILLAR, BARREL, PILLAR), spacing=31, speed=1.0, y=0),
)

CUES = {
    "agent_done": ("R..R", "BBBB"),       # the imp, down
    "job_done": (".P.", "PWP", ".P."),    # a health bonus
}

ASCII = {
    "hero": (" n ", "[o]", "|||"),
    "mover": ("v v", "(x)"),
    "tile": ("[#]", "[#]", "[#]"),
    "ground": ("#",),
}

DOOM = Scene(
    name="doom", colors=COLORS, ground=("MTMM",), hero=HERO, ascii=ASCII, hero_x=8,
    layers=LAYERS, mover=IMP, cues=CUES, scroll_phases=frozenset({"writing"}),
)
register_scene(DOOM)
