"""halo_harness.tui.scene_beetlejuice -- the Beetlejuice theme's level (Halo
3.0.2.0): the striped sand of the afterlife desert in a sandstorm, or a
haunted hillside under a dusk-purple sky. A yellow moon hangs far back, a crooked house and
dead trees creep by, tombstones and fog pass at ground speed, green
sparkles drift. The trickster in the striped suit (12 x 13: wild hair,
sunken eyes, a grin, black-and-white stripes) struts a six-frame stride
with his arms out while the model writes as a giant striped sandworm
surfaces and crosses; he conjures a ball of green sparks while the model
thinks as a bat flaps by; his head shrinks on an error; he holds up a
sign when it needs you. A baby sandworm pops up when a sub-agent
finishes, a waiting-room ticket flutters when a job completes. Original
art in the spirit of the film, nothing copied. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Particle, Scene, Shot, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "K": "#0c0c10", "W": "#ececf0", "C": "#b0b0b8", "P": "#7a35b8", "G": "#8cff4a", "S": "#d8dcc8",
    "H": "#a8d890", "E": "#2a1a3a", "R": "#d84060", "O": "#d89a50", "D": "#3a2050", "T": "#8a8a98",
    "B": "#4a3020", "Y": "#f0e080", "N": "#1a1030", "F": "#5a4a70", "L": "#ffd060", "M": "#6a2a9a",
    "X": "#f8f8ff", "I": "#c8c8d8",
}

# -- the trickster, 12 wide ----------------------------------------------------
_HAIR = (".HHHHHHHHHH.", "HHHhHHHHhHHH")
_FACE = (".HSSSSSSSSH.", ".SSEESSEESS.", ".SSSSSSSSSS.", "..SSRRRRSS..")
_JACKET = (("KWKWKWKWKWKW", "SWKWKWKWKWKS", "..KWKWKWKW..", "..KWKWKWKW.."),      # arms out
           ("KWKWKWKWKWKS", "KWKWKWKWKWKW", "S.KWKWKWKW..", "..KWKWKWKW.."),      # one arm swung
           ("SWKWKWKWKWKW", "KWKWKWKWKWKW", "..KWKWKWKW.S", "..KWKWKWKW.."))      # the other
_LEGS = (("..KWKW.KWKW.", "..KWK...WKW.", "..KKK...KKK."),   # contact
         ("..KWKWKW....", "..KWKKW.....", "..KKK.KKK..."),   # pass
         (".KWKW...KWKW", "KWK.....WKWK", "KKK......KKK"),   # stride
         ("...KWKWK....", "...KWKW.....", "..KKKKK....."),   # tuck
         (".KWKW...KWKW", "KWK.......WK", "KKK......KKK"),   # stride
         ("..KWKWKW....", "..KWK.KW....", "..KKK..KKK.."))   # pass
_STAND = _HAIR + _FACE + _JACKET[0] + _LEGS[0]
_RUN = tuple(_HAIR + _FACE + _JACKET[(1, 2, 0, 1, 2, 0)[i]] + _LEGS[i] for i in range(6))
_CONJURE = (_HAIR + _FACE + ("KWKWKWKWKWKS", "SWKWKWKWKWKW", "..KWKWKWKW..", "..KWKWKWKW..") + _LEGS[0],
            _HAIR + _FACE + ("KWKWKWKWKWKS", "SWKWKWKWKWK.", "..KWKWKWKW..", "..KWKWKWKW..") + _LEGS[0])
_SHRUNK = ("............", "............", "............", "....HHHH....", "....SEES....", "....SRRS....") + _JACKET[0] + _LEGS[0]
_SIGN = ("........XXXX", ".HHHHHHHXKKX", "HHHhHHHHXKKX", ".HSSSSSSXXXX", ".SSEESSEES..", ".SSSSSSSSSS.", "..SSRRRRSSS.",
         "KWKWKWKWKWKS", "SWKWKWKWKWK.", "..KWKWKWKW..") + _LEGS[0]
# Conjured green sparks fly from his hand while he struts; four of them sink the worm.
SPARKS = Shot(frames=(("GG", "gG"), ("gG", "GG")), speed=4, every=8, life=26, y=6, dx=1, light=("#8cff4a", 3))
HERO = {
    "idle": (_STAND, _HAIR + _FACE + _JACKET[0] + _LEGS[0]),
    "writing": _RUN,
    "thinking": _CONJURE,
    "error": (_SHRUNK,),
    "needs_you": (_SIGN, _SIGN, _STAND),
}

# -- the enemies ---------------------------------------------------------------
# The sandworm, 32 x 12: a striped body rising out of the sand in two
# humps, a huge open mouth ringed with teeth, a red tongue, beady eyes.
_WORM_HEAD = (".......KKKKKKKKKKK..............", ".....KKWWWWWWWWWKKKK............", "....KWWWKKKKKKKWWWKKKK..........",
              "...KWWKKEEKKKKKKKWWKKKKK........", "..KWWKWWWWWWWWWWWKWWKKKKKK......", "..KWKRRRRRRRRRRRRRKWKKKKKKK.....",
              "..KWKRRRRRRRRRRRRRKWWKKKKKKKK...", "..KWWKWWWWWWWWWWWKWKKKKKKKKKKK..")
SANDWORM = Mover(frames=(_WORM_HEAD + ("...KWWKKKKKKKKKKKWKKWWKKWWKKWWKK", ".....KKKKKKKKKKKKKKWWKKWWKKWWKKK", "........KKKKKKKKKKWWKKWWKKWWKKKK",
                                       "............KKKKKWWKKWWKKWWKKKKK"),
                         _WORM_HEAD + ("...KWWKKKKKKKKKKKWKKWWKKWWKKWWKK", ".....KKKKKKKKKKKKKWWKKWWKKWWKKKK", ".......KKKKKKKKKWWKKWWKKWWKKKKKK",
                                       "..........KKKKKWWKKWWKKWWKKKKKKK")),
                 phases=frozenset({"writing", "thinking"}), speed=2, y=0, bob=1)
# A bat, 9 x 4, two flaps.
BAT = Mover(frames=(("K.......K", "KK.KKK.KK", ".KKKRKKK.", "...K.K..."), ("....K....", ".KKKKKKK.", "KK.KRK.KK", "K..K.K..K")),
            phases=frozenset({"thinking"}), speed=3, y=8, bob=1)

# -- scenery -------------------------------------------------------------------
MOON = ("..YYYY..", ".YYYYYY.", "YYYYYYYY", "YYYYYYYY", ".YYYYYY.", "..YYYY..")
HOUSE = ("......NN......", ".....NNNN.....", "....NNNNNN....", "...NNNNNNNN...", "..NNNNNNNNNN..", ".NNNNNNNNNNNN.",
         "NNNNNNNNNNNNNN", "NNNNNNLLNNNNNN", "NNNNNNLLNNNNNN", "NNNNNNNNNNNNNN", "NNNNNNNNNNNNNN")
TREE = ("B...B..B", ".B.B..B.", "..BB.B..", "...BB...", "...BB...", "...BB...", "..BBBB..")
TOMB = ("TTTT", "TtTT", "TTtT", "TTTT", "TTTT")
CROSS = (".T.", "TTT", ".T.", ".T.", ".T.")
FOG = ("FFFFFFFFFF", "fFFFFFFFFf")
SPARK = (("G",), ("g",))
CONJURE = (("G",), ("GG",), ("G",))

LAYERS = (
    Layer(sprites=(MOON,), spacing=173, speed=0.03, y=7),
    Layer(sprites=(HOUSE,), spacing=131, speed=0.2, y=0),
    Layer(sprites=(TREE,), spacing=53, speed=0.5, y=0),
    Layer(sprites=(TOMB, CROSS, TOMB), spacing=47, speed=1.0, y=0),
    Layer(sprites=(FOG,), spacing=31, speed=0.3, y=0, twinkle=4),
)
SAND = (("o",), ("O",), ("o",), ("o.o",))
PARTICLES = (
    # the sandstorm on Saturn: grains tearing left across the whole band
    Particle(frames=SAND, every=1, life=22, anchor="world", y=1, spread_x=40, spread_y=13, dx=-3.2, vy=0.05,
             variants=frozenset({"saturn"})),
    Particle(frames=(("oo",), ("ooo",), ("oo",)), every=1, life=20, anchor="world", y=3, spread_x=60, spread_y=11,
             dx=-4.0, vy=0.0, variants=frozenset({"saturn"})),
    Particle(frames=(("O",), ("o",)), every=1, life=18, anchor="world", y=0, spread_x=20, spread_y=14, dx=-2.4,
             vy=0.1, variants=frozenset({"saturn"})),
    Particle(frames=SPARK, every=5, life=20, anchor="world", y=2, spread_y=6, dx=-0.1, vy=0.25, light=("#8cff4a", 1)),
    Particle(frames=CONJURE, every=2, life=6, anchor="hero", x=11, y=9, spread_x=2, spread_y=2, vy=0.4,
             phases=frozenset({"thinking"}), light=("#8cff4a", 4)),
)

GRAVE = (("DdDDDdDDDDdD", "KdKKKKdKKKKd", "KKKKKKKKKKKK"),)
DUNES = (("OoOOOOoOOOOo", "oOOOoOOOoOOO", "oooooooooooo"),)

CUES = {
    "agent_done": (("..KK..", ".KWWK.", "KWEEWK", "KRRRRK"), ("..KK..", ".KWWK.", "KWEEWK", "KRRRRK", "KWWWWK"),
                   ("..KK..", ".KWWK.", "KWEEWK", "KRRRRK", "KWWWWK", "KKKKKK")),
    "job_done": (("XXXXX", "XKKKX", "XXXXX"), ("XXXXX", "XK.KX", "XXXXX")),
}
CUE_RISE = {"agent_done": (0, 1, 2, 2), "job_done": (0, 1, 2, 3, 3, 2)}

ASCII = {
    "hero": (" # ", "(o)", "|#|", "|#|", "/ \\"),
    "mover": ("~~O", "~~~~", "~~~~"),
    "tile": ("+", "|", "|", "|"),
    "ground": ("_",),
}

VARIANTS = {
    "saturn": {"N": "#5a2a50", "F": "#e0a060", "T": "#c8a070", "B": "#6a4a30"},
    "house": {},
}
SKIES = {
    "house": gradient("#160c24", "#5a2a70"),
    "saturn": gradient("#3a1a40", "#c06a30"),
}

BEETLEJUICE = Scene(
    name="beetlejuice", colors=COLORS, ground=DUNES, hero=HERO, ascii=ASCII, hero_x=16,
    layers=LAYERS, mover=SANDWORM, movers=(BAT,), cues=CUES, cue_rise=CUE_RISE, scroll_phases=frozenset({"writing"}),
    variants=VARIANTS, sky=SKIES["saturn"], skies=SKIES, grounds={"house": GRAVE, "saturn": DUNES}, particles=PARTICLES,
    hero_shot=SPARKS,
)
register_scene(BEETLEJUICE)
