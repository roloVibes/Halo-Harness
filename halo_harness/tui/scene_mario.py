"""halo_harness.tui.scene_mario -- the Mario theme's level (Halo 3.0.2.0,
second generation): a bright overworld under a dusk-blue sky. Far hills
drift slowly, clouds a little faster, bushes and warp pipes at ground
speed; a brick row with a question block hangs above; coins twinkle. The
plumber runs a four-frame stride and hops every two seconds while the
model writes; a winged turtle glides by flapping; a 1-UP mushroom pops up
when a sub-agent finishes, a coin when a background job completes. Looks
up with a "?" while the model thinks, flattens on an error, waves when it
needs you. Original art, nothing copied from any game. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Scene, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "R": "#e63946", "S": "#f6cfa0", "B": "#2f62d6", "K": "#3a2210", "Y": "#f8d040", "W": "#f4f6ff",
    "G": "#2fa84f", "L": "#8ff09a", "O": "#c9733a", "D": "#7a3f1a", "Q": "#f3b31a", "H": "#3d9a4a",
    "C": "#eef2ff", "E": "#1b1b1b", "T": "#fff6a0",
}

# The plumber, 8 x 9: cap, sideburn, eye, red shirt, blue overalls with a
# button, shoes. Lowercase = shadow (auto-derived).
_HEAD = ("..RRRRR.", ".RRRRRRr", "..SSKKS.", ".SSSSESS", "..SSSss.")
_BODY = (".RBBBBR.", "RrBYBBrR")
_LEGS = ((".BBBbbb.", ".KK..KK."), ("..BBbb..", "..KKK..."), (".BBBbbb.", "KK....KK"), ("..BBbb..", "..KKK..."))
_STAND = _HEAD + _BODY + (".BBBbbb.", ".KK..KK.")
_QUEST = ("..RRRRR...", ".RRRRRRr..", "..SSKKS.TT", ".SSSSESS.T", "..SSSss.T.", ".RBBBBR...", "RrBYBBrR.T", ".BBBbbb...", ".KK..KK...")
HERO = {
    "idle": (_STAND,),
    "writing": tuple(_HEAD + _BODY + legs for legs in _LEGS),
    "thinking": (_QUEST, _STAND),
    "error": (("..RRRRR.", ".RRRRRRr", "..SESES.", ".SSSSSSS", ".RBBBBR.", "RrBBBBrR", ".KK..KK."),),
    "needs_you": (_STAND, ("..RRRRR..", ".RRRRRRr.", "..SSKKS.S", ".SSSSESSS", "..SSSss.R", ".RBBBBRR.", "RrBYBBrR.", ".BBBbbb..", ".KK..KK..")),
}
JUMP = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 4, 5, 5, 4, 3, 1)   # a hop every ~2 s at 8 fps

# The winged turtle, 10 x 6, three wing frames; it glides above the ground.
TURTLE = Mover(frames=(("..W.......", ".WWW..GG..", "WWGGGGGGY.", ".GGgGGgYYY", "..YY.YY.Y.", "..Y..Y...."),
                       ("..........", "......GG..", "WWWGGGGGY.", "WWGgGGgYYY", "..YY.YY.Y.", "..Y..Y...."),
                       ("..........", "......GG..", "..GGGGGGY.", "WWGgGGgYYY", "WWYY.YY.Y.", "..Y..Y....")),
               phases=frozenset({"writing"}), speed=2, y=3, bob=1)

HILL = ("......HHHH......", "....HHHHHHHH....", "..HHHhHHHHhHHH..", "HHHHHHHHHHHHHHHH")
CLOUD = ("..CCC...", ".CCCCCC.", "CCCCCCCC", ".cccccc.")
CLOUD_SMALL = (".CCC.", "CCCCC", ".ccc.")
BUSH = ("..GGG..", ".GGGGG.", "GGgGGgG")
PIPE_TALL = ("LLGGGGgl", "LLGGGGgl", ".LGGGGg.", ".LGGGGg.", ".LGGGGg.", ".LGGGGg.", ".LGGGGg.")
PIPE_SHORT = ("LLGGGGgl", "LLGGGGgl", ".LGGGGg.", ".LGGGGg.")
BLOCKS = ("ODDOODDOQQQQODDOODDO", "DOODDOODQYYQDOODDOOD", "ddddddddqqqqdddddddd")
COIN = ("YY", "Yy", "yy")
STAR = ("T",)

LAYERS = (
    Layer(sprites=(STAR,), spacing=17, speed=0.1, y=8, twinkle=2),
    Layer(sprites=(HILL,), spacing=71, speed=0.3, y=0),
    Layer(sprites=(CLOUD, CLOUD_SMALL), spacing=53, speed=0.5, y=5),
    Layer(sprites=(BUSH,), spacing=67, speed=1.0, y=0),
    Layer(sprites=(BLOCKS,), spacing=131, speed=1.0, y=6),
    Layer(sprites=(COIN,), spacing=41, speed=1.0, y=4, twinkle=3),
    Layer(sprites=(PIPE_TALL, PIPE_SHORT, PIPE_SHORT), spacing=59, speed=1.0, y=0),
)

GROUND = (("LLLLLLLL", "OOOODOOO", "DdDDDdDD"),)

CUES = {
    "agent_done": ("..GG.", ".GWGG", "GGGWG", ".SSS.", ".sss."),   # the 1-UP mushroom
    "job_done": (".YY.", "YQQY", "YQQY", ".yy."),                 # a coin
}

ASCII = {
    "hero": (" n ", "(o)", "/|\\", "|||"),
    "mover": ("<=>", "(oo)", " vv "),
    "tile": ("[==]", "|  |", "|  |", "|  |"),
    "ground": ("=",),
}

VARIANTS = {
    "bros": {},
    "world": {"G": "#3cc25c", "L": "#a0f0a8", "O": "#e08a3a", "Q": "#ffd23a", "H": "#55b86a", "C": "#ffffff"},
}
SKIES = {
    "bros": gradient("#0e1830", "#2454a8"),
    "world": gradient("#10305e", "#3b7fd6"),
}

MARIO = Scene(
    name="mario", colors=COLORS, ground=GROUND, hero=HERO, ascii=ASCII, hero_x=10,
    layers=LAYERS, mover=TURTLE, cues=CUES, scroll_phases=frozenset({"writing"}), variants=VARIANTS,
    sky=SKIES["bros"], skies=SKIES, jump=JUMP,
)
register_scene(MARIO)
