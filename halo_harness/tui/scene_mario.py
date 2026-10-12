"""halo_harness.tui.scene_mario -- the Mario theme's level (Halo 3.0.2.0,
third generation): a bright overworld, sixteen pixels tall. Far mountains
and hills drift slowly, clouds a little faster, bushes, pipes with lips, a
brick row with a flashing question block and spinning coins at ground
speed. The plumber (12 x 14, cap, moustache, gloves, overalls with
buttons) runs a six-frame stride with swinging arms, dust at his heels,
and hops every two seconds while the model writes; a shroom walker
trundles by in the writing phase, a winged turtle flaps across while the
model thinks and the plumber looks up with a "?". He flattens on an
error, waves when it needs you. A mushroom pops out of a block when a
sub-agent finishes, a coin spins up when a job completes. Original art,
nothing copied from any game. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Particle, Scene, Shot, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "R": "#e83a3a", "S": "#f8c89a", "K": "#4a2810", "M": "#2a160a", "B": "#2d5fe0", "Y": "#f8d040",
    "W": "#fafaff", "G": "#2fa84f", "L": "#8ff09a", "O": "#c9733a", "D": "#7a3f1a", "Q": "#f3b31a",
    "H": "#3d9a4a", "C": "#f4f8ff", "c": "#b8c8e8", "T": "#fff6a0", "N": "#b06a2a", "F": "#f3d6a6",
    "I": "#2a4a7a", "U": "#6a8ad0", "X": "#e0d8c8", "E": "#141018", "V": "#5bd47a",
}

# -- the plumber, 12 wide ----------------------------------------------------
_CAP = ("....RRRRR...", "...RRRRRRRR.", "...KKSSSKS..")
_FACE = ("..KSSSSKSSS.", "..KSsMMSSS..", "...SSSSSs...")
_TORSO = (("..RRBRRRRR..", ".RRRBBBBRRR.", ".WWBBYBBYWW.", "..WBBBBBBW.."),   # arms down
          ("..RRBRRRRR..", "WRRRBBBBRRRW", "WWBBBYBBYBWW", "...BBBBBB..."),   # arms swung
          ("..RRBRRRRR..", ".RRRBBBBRRRW", ".WWBBYBBYBWW", "..WBBBBBB..."))   # one arm forward
_LEGS = (("...BBB.BBB..", "..KKK..KKK..", ".KKKK..KKKK."),   # contact
         ("...BBBBB....", "..KKKBB.....", ".KKKK.KKK..."),   # pass
         ("..BBB...BBB.", ".KKK.....KKK", "KKKK.....KKK"),   # stride
         ("...BBBBB....", "....KKKK....", "...KKKKK...."),   # tuck
         ("..BBB...BBB.", "KKK......KKK", "KKKK....KKKK"),   # stride
         ("...BBBBB....", "..KKK.KK....", ".KKKK..KK..."))   # pass
_STAND = _CAP + _FACE + _TORSO[0] + _LEGS[0]
_RUN = tuple(_CAP + _FACE + _TORSO[(1, 2, 0, 1, 2, 0)[i]] + _LEGS[i] for i in range(6))
_THINK_A = ("....RRRRR..T", "...RRRRRRRRT", "...KKSSSKS.T", "..KSSSSKSSS.", "..KSsMMSSS..", "...SSSSSsW..",
            "..RRBRRRRWW.", ".RRRBBBBRRR.", ".WWBBYBBYR..", "..WBBBBBBW..") + _LEGS[0]
_THINK_B = ("....RRRRR.TT", "...RRRRRRRRT", "...KKSSSKS..", "..KSSSSKSSS.", "..KSsMMSSS..", "...SSSSSsW..",
            "..RRBRRRRWW.", ".RRRBBBBRRR.", ".WWBBYBBYR..", "..WBBBBBBW..") + _LEGS[0]
_FLAT = ("...RRRRRRRRR..", "..KKSSMSSMSKK.", ".RRRBBBBBBBRRR", "WWWBBYBBBYBWWW", ".KKKKKK.KKKKKK")
_WAVE_A = ("....RRRRR..W", "...RRRRRRRRW", "...KKSSSKS.R", "..KSSSSKSSSR", "..KSsMMSSS.R", "...SSSSSs.R.",
           "..RRBRRRRRR.", ".RRRBBBBRR..", ".WWBBYBBYB..", "..WBBBBBB...") + _LEGS[0]
_WAVE_B = ("....RRRRR.W.", "...RRRRRRRW.", "...KKSSSKSR.", "..KSSSSKSSR.", "..KSsMMSSSR.", "...SSSSSsR..",
           "..RRBRRRRR..", ".RRRBBBBRR..", ".WWBBYBBYB..", "..WBBBBBB...") + _LEGS[0]
HERO = {
    "idle": (_STAND, _CAP + _FACE + _TORSO[0] + _LEGS[0]),
    "writing": _RUN,
    "thinking": (_THINK_A, _THINK_A, _THINK_B, _THINK_B),
    "error": (_FLAT,),
    "needs_you": (_WAVE_A, _WAVE_B),
}
JUMP = (0,) * 10 + (2, 4, 6, 7, 7, 6, 4, 2)   # a hop every ~2 s at 8 fps
# Fireballs (the flower power): they bounce along ahead of him and take the walker down in four.
FIREBALL = Shot(frames=(("QY", "YQ"), ("YQ", "QY")), speed=4, every=9, life=26, y=4, dx=1, light=("#f8d040", 2))

# -- the enemies ---------------------------------------------------------------
# A shroom walker, 10 x 8: brown cap, cream face with a frown, two feet.
WALKER = Mover(frames=(("...NNNN...", ".NNNNNNNN.", "NNNnNNnNNN", "NNNNNNNNNN", ".FFMFFMFF.", ".FFFFFFFF.",
                        "..MM..MM..", ".MMM..MMM."),
                       ("...NNNN...", ".NNNNNNNN.", "NNNnNNnNNN", "NNNNNNNNNN", ".FFMFFMFF.", ".FFFFFFFF.",
                        "..MM..MM..", "..MMM.MMM."),
                       ("...NNNN...", ".NNNNNNNN.", "NNNnNNnNNN", "NNNNNNNNNN", ".FFMFFMFF.", ".FFFFFFFF.",
                        "..MM..MM..", ".MMM..MMM."),
                       ("...NNNN...", ".NNNNNNNN.", "NNNnNNnNNN", "NNNNNNNNNN", ".FFMFFMFF.", ".FFFFFFFF.",
                        "..MM..MM..", "MMM...MMM.")),
               phases=frozenset({"writing"}), speed=1, y=0)
# A winged turtle, 12 x 8, three wing beats; it glides above the ground.
TURTLE = Mover(frames=(("..WW........", ".WWWW..GGG..", "WWWWGGGGGGV.", ".WWGGgGGgVVV", "..GGgGGGgVV.", "...YYYYYY.V.",
                        "...Y..Y.....", "...Y..Y....."),
                       ("............", "......GGG...", "WWWWGGGGGGV.", "WWWGGgGGgVVV", "..GGgGGGgVV.", "...YYYYYY.V.",
                        "...Y..Y.....", "..YY..YY...."),
                       ("............", "......GGG...", "....GGGGGGV.", "WWWGGgGGgVVV", "WWWWgGGGgVV.", "..WYYYYYY.V.",
                        "...Y..Y.....", "...Y..Y.....")),
               phases=frozenset({"thinking"}), speed=2, y=4, bob=1)

# -- scenery -------------------------------------------------------------------
MOUNTAIN = ("........IIII........", "......IIIIIIII......", "....IIIIIUUIIII.....", "..IIIIIIUUUUIIII....",
            "IIIIIIIIIIIIIIIIIIII", "IIIIIIIIIIIIIIIIIIII")
HILL = ("......HHHH......", "....HHHHHHHH....", "..HHHhHHHHhHHH..", "HHHHHHHHHHHHHHHH", "HHHHHHHHHHHHHHHH")
CLOUD = ("...CCCC.....", ".CCCCCCCC...", "CCCCCCCCCCC.", "CCCCCCCCCCCC", ".ccccccccccc")
CLOUD_SMALL = ("..CCC..", ".CCCCCC", "CCCCCCC", ".cccccc")
BUSH = ("...GGGG...", ".GGGGGGGG.", "GGgGGGGgGG", "GGGGgGGGGG")
PIPE_TALL = ("LLGGGGGGgl", "LLGGGGGGgl", ".LLGGGGg..", ".LLGGGGg..", ".LLGGGGg..", ".LLGGGGg..", ".LLGGGGg..",
             ".LLGGGGg..", ".LLGGGGg..")
PIPE_SHORT = ("LLGGGGGGgl", "LLGGGGGGgl", ".LLGGGGg..", ".LLGGGGg..", ".LLGGGGg..")
BRICKS_A = ("OODOOODOOOQQQQQOODOOODOO", "DOODDOODDOQTYTQDOODDOODD", "OODOOODOOOQYYYQOODOOODOO", "dddddddddddqqqqddddddddd")
BRICKS_B = ("OODOOODOOOQQQQQOODOOODOO", "DOODDOODDOQYTYQDOODDOODD", "OODOOODOOOQTTTQOODOOODOO", "dddddddddddqqqqddddddddd")
COIN_A, COIN_B, COIN_C, COIN_D = ("YYY", "YTY", "YYY"), (".YY", ".YT", ".YY"), ("..Y", "..y", "..Y"), ("yY.", "Ty.", "yY.")
STAR = ("T",)
DUST = (("X",), ("XX",), ("X.X",), ("x",))

LAYERS = (
    Layer(sprites=(STAR,), spacing=19, speed=0.05, y=11, twinkle=2),
    Layer(sprites=(MOUNTAIN,), spacing=97, speed=0.15, y=0),
    Layer(sprites=(HILL,), spacing=73, speed=0.3, y=0),
    Layer(sprites=(CLOUD, CLOUD_SMALL, CLOUD), spacing=57, speed=0.5, y=8),
    Layer(sprites=(BUSH,), spacing=67, speed=1.0, y=0),
    Layer(sprites=(BRICKS_A, BRICKS_B), spacing=151, speed=1.0, y=8, animate=4),
    Layer(sprites=(COIN_A, COIN_B, COIN_C, COIN_D), spacing=43, speed=1.0, y=5, animate=2),
    Layer(sprites=(PIPE_TALL, PIPE_SHORT, PIPE_SHORT), spacing=61, speed=1.0, y=0),
)
PARTICLES = (
    Particle(frames=DUST, every=3, life=6, anchor="hero", x=-2, y=0, spread_x=2, dx=-1.5, vy=0.6, gravity=0.08,
             phases=frozenset({"writing"})),
)

GROUND = (("LLLLLLLLLLLL", "OOODOOOOODOO", "DdDDDdDDDDdD"),)

CUES = {   # the mushroom rises out of a bumped block; the coin spins up
    "agent_done": (("QQQQQ", "QyyyQ", "QyyyQ", "QQQQQ"),
                   (".RRR.", "QRWRQ", "QyyyQ", "QQQQQ"),
                   ("..RRR..", ".RWRRW.", "RRRRWRR", ".SSSSS.", ".sSSSs."),
                   ("..RRR..", ".RWRRW.", "RRRRWRR", ".SSSSS.", ".sSSSs."),
                   ("..RRR..", ".RWRRW.", "RRRRWRR", ".SSSSS.", ".sSSSs.")),
    "job_done": (("YYY", "YTY", "YYY"), (".YY", ".YT", ".YY"), ("..Y", "..y", "..Y"), ("yY.", "Ty.", "yY."),
                 ("YYY", "YTY", "YYY"), ("T.T", ".Y.", "T.T")),
}
CUE_RISE = {"agent_done": (0, 1, 2, 3, 3, 3), "job_done": (0, 2, 4, 6, 7, 8, 8)}

ASCII = {
    "hero": (" n ", "(o)", "/|\\", "|||", "/ \\"),
    "mover": ("<=>", "(oo)", " vv "),
    "tile": ("[==]", "|  |", "|  |", "|  |", "|  |"),
    "ground": ("=",),
}

VARIANTS = {
    "bros": {},
    "world": {"G": "#3cc25c", "L": "#a0f0a8", "O": "#e08a3a", "Q": "#ffd23a", "H": "#55b86a", "I": "#4a3a7a", "U": "#8a7ad0"},
}
SKIES = {
    "bros": gradient("#3a78e8", "#8ec8ff"),
    "world": gradient("#2a2a6e", "#c070a0"),
}

MARIO = Scene(
    name="mario", colors=COLORS, ground=GROUND, hero=HERO, ascii=ASCII, hero_x=16,
    layers=LAYERS, mover=WALKER, movers=(TURTLE,), cues=CUES, cue_rise=CUE_RISE,
    scroll_phases=frozenset({"writing"}), variants=VARIANTS, sky=SKIES["bros"], skies=SKIES, jump=JUMP,
    particles=PARTICLES, hero_shot=FIREBALL,
)
register_scene(MARIO)
