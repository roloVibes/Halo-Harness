"""halo_harness.tui.scene_mario -- the Mario theme's level (Halo 2.0.11
round A3): a plumber in a red cap running past warp pipes, brick rows and
question blocks under drifting clouds, a winged turtle gliding by while
the model writes, a 1-UP mushroom when a sub-agent finishes and a spinning
coin when a background job completes. Original art in the spirit of the
8-bit overworld; nothing here is copied from any game. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Scene, register_scene

COLORS = {
    "R": "#e63946", "S": "#f2c38f", "B": "#2f62d6", "K": "#4a2a10", "Y": "#f8d040",
    "G": "#2fa84f", "L": "#7fe08a", "W": "#f4f6ff", "O": "#c9733a", "D": "#7a3f1a", "Q": "#f3b31a",
}

# The plumber: 5 x 5, cap, face with an eye, red arms over blue overalls.
HERO = {
    "idle": ((".RRR.", ".SSK.", "RBBBR", ".BBB.", ".K.K."),),
    "writing": ((".RRR.", ".SSK.", "RBBBR", ".BBB.", "K...K"),
                (".RRR.", ".SSK.", ".BBBR", "RBBB.", ".KK..")),
    "thinking": ((".RRR.", ".SSK.", "RBBBR", ".BBB.", ".K.K."),
                 (".RRR.", ".KSS.", "RBBBR", ".BBB.", ".K.K.")),
    "error": (("....." , ".....", ".RRR.", "RSSKR", "KBBBK"),),
    "needs_you": ((".RRR.", ".SSKR", ".BBB.", ".BBB.", ".K.K."),
                  (".RRRR", ".SSK.", "RBBB.", ".BBB.", ".K.K.")),
}

# The winged turtle, two wing frames; it glides above the ground.
TURTLE = Mover(frames=(("..W...", ".WGGY.", "WGGGYY", "..Y.Y."),
                       ("......", "..GGY.", "WWGGYY", ".WY.Y.")),
               phases=frozenset({"writing"}), speed=2, y=1)

PIPE_TALL = ("LGGGGL", ".LGGL.", ".LGGL.", ".LGGL.")
PIPE_SHORT = ("LGGGGL", ".LGGL.", ".LGGL.")
BLOCKS = ("ODOODOODQQQ", "DOODOODOQDQ")
CLOUD = (".WW.", "WWWW")

LAYERS = (
    Layer(sprites=(CLOUD,), spacing=61, speed=0.4, y=4),
    Layer(sprites=(BLOCKS,), spacing=97, speed=1.0, y=3),
    Layer(sprites=(PIPE_TALL, PIPE_SHORT), spacing=43, speed=1.0, y=0),
)

CUES = {
    "agent_done": ("GWG", "GGG", ".SS."),   # the 1-UP mushroom
    "job_done": (".Y.", "YQY", ".Y."),      # a coin
}

ASCII = {
    "hero": (" n ", "(o)", "|||"),
    "mover": ("<=>", " v "),
    "tile": ("[==]", "|  |", "|  |"),
    "ground": ("=",),
}

VARIANTS = {
    "bros": {},
    "world": {"G": "#3cc25c", "L": "#a0f0a8", "O": "#e08a3a", "Q": "#ffd23a"},
}

MARIO = Scene(
    name="mario", colors=COLORS, ground=("ODOD",), hero=HERO, ascii=ASCII, hero_x=8,
    layers=LAYERS, mover=TURTLE, cues=CUES, scroll_phases=frozenset({"writing"}), variants=VARIANTS,
)
register_scene(MARIO)
