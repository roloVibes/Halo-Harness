"""halo_harness.tui.scene_metroid -- the Metroid theme's level (Halo 3.0.2.0,
third generation): a deep cavern, sixteen pixels tall, that darkens toward
the floor. Far wall silhouettes creep by, stalactites drip, spores drift
up and glow, rock columns and a blue hatch pass at ground speed. The
hunter in a power suit (12 x 14: round helmet, green visor, pauldrons,
arm cannon) runs a six-frame stride and fires charge-beam bolts that
light the rock while the model writes; the cannon charges with a pulsing
glow while the model thinks as a floating alien drifts in; a spiny
crawler scuttles by in the writing phase; the alien latches onto the
helmet on an error; the visor beacon blinks when it needs you. An energy
tank rises when a sub-agent finishes, a missile pickup when a job
completes. The area sets the floor and the sky: rock in Crateria, growth
in Brinstar, lava in Norfair, water in Maridia, machine floor in Tourian.
Original art, nothing copied from any game. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Particle, Scene, Shot, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "O": "#f0801c", "Y": "#ffc83c", "V": "#5de06a", "A": "#a0a8b8", "E": "#ffb020", "G": "#7df27d",
    "R": "#e33b3b", "F": "#f4f6ff", "K": "#332a4e", "M": "#564a78", "B": "#3a7bd5", "T": "#4fd1c5",
    "P": "#1a1236", "Z": "#9ff3ff", "g": "#4a4660", "k": "#302c40", "L": "#ff6a1a", "l": "#ffc020",
    "D": "#8c3fd8", "S": "#1b2f45", "W": "#6fb7ff", "N": "#3f8f4f", "Q": "#241a3c",
}

# -- the hunter, 12 wide -------------------------------------------------------
_HELMET = ("....OOOO....", "...OOYOOO...", "...OVVVVO...", "...OVvvVO...", "....OOOO....")
_ARMS = (("..YYOOOOYY..", ".YYYOOOOYYAA", ".YyOOOOOOAAa", "..OORROOO..."),    # cannon level
         ("..YYOOOOYY..", ".YYYOOOOYYAa", ".YyOOOOOOAAA", "..OORROOO..."),    # recoil
         ("..YYOOOOYY..", ".YYYOOOOYYA.", ".YyOOOOOOAAA", "..OORROOOA.."))    # cannon dipped
_LEGS = (("...OOOOOO...", "...OOO.OOO..", "..OOO...OOO.", "..ooo...ooo."),   # contact
         ("...OOOOOO...", "...OOOOO....", "..OOOOO.....", "..ooo.ooo..."),   # pass
         ("...OOOOOO...", "..OOO...OOO.", ".OOO.....OOO", ".ooo.....ooo"),   # stride
         ("...OOOOOO...", "....OOOO....", "...OOOOO....", "...oooo....."),   # tuck
         ("...OOOOOO...", "..OOO...OOO.", "OOO.......OO", "ooo.......oo"),   # stride
         ("...OOOOOO...", "...OOOOO....", "..OO..OOO...", "..oo...ooo.."))   # pass
_STAND = _HELMET + _ARMS[0] + _LEGS[0]
_RUN = tuple(_HELMET + _ARMS[(1, 0, 0, 2, 0, 0)[i]] + _LEGS[i] for i in range(6))
_CHARGE = tuple(_HELMET + arms + _LEGS[0] for arms in (_ARMS[0], _ARMS[2]))
_LATCHED = (".GGGGGGGGGG.", "GGRGGGGGGRGG", ".GgGGGGGGgG.", "..GgGgGgGg..", "...OOOO.....") + _ARMS[0] + _LEGS[0]
_BEACON = ("....EEEE....", "...OEEEEO...", "...OVVVVO...", "...OVvvVO...", "....OOOO....") + _ARMS[0] + _LEGS[0]
HERO = {
    "idle": (_STAND, _HELMET + _ARMS[2] + _LEGS[0]),
    "writing": _RUN,
    "thinking": _CHARGE,
    "error": (_LATCHED,),
    "needs_you": (_STAND, _BEACON),
}

# The charge beam: bolts fly right while the model writes and light the rock.
BEAM = Shot(frames=(("ZZZZZ", "zZZZz"), ("zZZZZ", "ZZZzz")), speed=5, every=8, life=28, y=7, dx=1, light=("#9ff3ff", 4))

# -- the enemies ---------------------------------------------------------------
# The alien, 13 x 10: a round green dome with a membrane highlight, four
# red nuclei in a cluster inside, and four fangs hanging from the rim.
ALIEN = Mover(frames=(("....GGGGG....", "..GGGGGGGGG..", ".GGGGGgGGGGG.", "GGGRRGGGRRGGG", "GGGRRGRGRRGGG", "GGGGGGRRGGGGG",
                       ".GGGGGGGGGGG.", "..gGgGgGgGg..", "..F..F.F..F..", "..F..F.F..F.."),
                      ("....ggggg....", "..GGGGGGGGG..", ".GGGGGGGGGGG.", "GGGRRGGGRRGGG", "GGGRRGRGRRGGG", "GGGGGGRRGGGGG",
                       ".GGGGgGGGGGG.", "..GgGgGgGgG..", "..F..F.F..F..", "...F.F.F.F...")),
              phases=frozenset({"thinking", "writing"}), speed=1, y=3, bob=2)
# A spiny crawler, 10 x 6: a purple shell with spikes, scuttling on short legs.
CRAWLER = Mover(frames=(("..D.DD.D..", ".DDDDDDDD.", "DDdDDDDdDD", "DDDDDDDDDD", ".DDDDDDDD.", ".kk.kk.kk."),
                        ("..D.DD.D..", ".DDDDDDDD.", "DDdDDDDdDD", "DDDDDDDDDD", ".DDDDDDDD.", "kk.kk.kk..")),
                phases=frozenset({"writing"}), speed=1, y=0)

# -- scenery -------------------------------------------------------------------
WALL = ("....QQQQ......", "...QQQQQQ..QQ.", "..QQQQQQQ.QQQQ", "..QQQQQQQQQQQQ", ".QQQQQQQQQQQQQ", "QQQQQQQQQQQQQQ",
        "QQQQQQQQQQQQQQ", "QQQQQQQQQQQQQQ", "QQQQQQQQQQQQQQ", "QQQQQQQQQQQQQQ", "QQQQQQQQQQQQQQ")
STALACTITE = ("MMMMMMM", "MMmMMmM", ".MMMMM.", "..MMM..", "..mMm..", "...m...")
SPORE = ("T",)
COLUMN = (".KMMK.", ".KMMMK", "KKMMMK", "KkMMMK", "KkMmMK", "KkMmMK", "KKMMMK", "KKmmmK", "KKMMMK", "KKmmmK")
BOULDER = (".MMMM.", "MMmMMM", "MmmMmM", "kMmmmk")
HATCH = ("BBBBBBBB", "BbEEEEbB", "BbEWWEbB", "BbEWWEbB", "BbEWWEbB", "BbEWWEbB", "BbEEEEbB", "BbEEEEbB", "bbbbbbbb")
DRIP = (("Z",), ("z",))
SPORE_DRIFT = (("t",), ("T",), ("t",))
CHARGE_GLOW = (("Z",), ("ZZ",), ("Z",))

LAYERS = (
    Layer(sprites=(WALL,), spacing=47, speed=0.25, y=0),
    Layer(sprites=(STALACTITE,), spacing=31, speed=0.6, y=9),
    Layer(sprites=(SPORE,), spacing=23, speed=0.8, y=6, twinkle=3, light=("#4fd1c5", 2)),
    Layer(sprites=(HATCH,), spacing=127, speed=1.0, y=0),
    Layer(sprites=(COLUMN, BOULDER, COLUMN, BOULDER, COLUMN), spacing=41, speed=1.0, y=0),
)
PARTICLES = (
    Particle(frames=SPORE_DRIFT, every=4, life=24, anchor="world", y=1, spread_y=4, dx=0.1, vy=0.35, light=("#4fd1c5", 1)),
    Particle(frames=DRIP, every=11, life=9, anchor="world", y=15, gravity=0.2, vy=0.0),
    Particle(frames=CHARGE_GLOW, every=2, life=4, anchor="hero", x=11, y=7, spread_x=1, spread_y=1,
             phases=frozenset({"thinking"}), light=("#9ff3ff", 3)),
)

ROCK = (("MMmMMMmMMMmM", "KkKKkKKKKkKK", "kKKKKkKKKKKk"),)
LAVA = (("LlLLLlLLLLlL", "LLLlLLLLlLLL", "llllllllllll"),
        ("LLlLLLlLLlLL", "lLLLLlLLLLlL", "llllllllllll"),
        ("LLLlLLLLLlLL", "LlLLlLLLLLLl", "llllllllllll"))
WATER = (("WTWWWTWWWWTW", "SSSSSSSSSSSS", "ssssssssssss"), ("WWTWWWWTWWWW", "SSSSSSSSSSSS", "ssssssssssss"))
GROWTH = (("NNnNNNnNNNnN", "KkKKkKKKKkKK", "kKKKKkKKKKKk"),)
METAL = (("AaAAAAaAAAAa", "kKKKKkKKKKKk", "kkkkkkkkkkkk"),)

CUES = {
    "agent_done": (("EEEEE", "EOOOE", "EOOOE", "EEEEE"), ("EEEEE", "EOYOE", "EOOOE", "EEEEE"), ("EEEEE", "EYYYE", "EOYOE", "EEEEE")),
    "job_done": ((".R.", "RRR", "FFF", "F.F"), (".R.", "RRR", "FFF", "FFF")),
}
CUE_RISE = {"agent_done": (0, 1, 2, 3, 4, 4), "job_done": (0, 1, 2, 2, 2)}

ASCII = {
    "hero": (" A ", "[o]", "/|=", "|||", "/ \\"),
    "mover": ("(oo)", " vv "),
    "tile": (" ||", " ||", " ||", " ||", "_||"),
    "ground": ("-",),
}

VARIANTS = {
    "crateria": {},
    "brinstar": {"g": "#3f8f4f", "k": "#2a5e34", "K": "#1f3a24", "M": "#356b3d", "Q": "#0f2416"},
    "norfair": {"K": "#3a1a10", "M": "#6b3220", "Q": "#2a110c"},
    "maridia": {"g": "#2b6fd6", "k": "#1a4aa0", "K": "#1a2a4a", "M": "#2f4f8a", "Q": "#0c2238"},
    "tourian": {"g": "#6a6f78", "k": "#4a4f57", "K": "#2a2c30", "M": "#45484f", "Q": "#1a1b1e"},
}
SKIES = {
    "crateria": gradient("#140d2a", "#07040f"),
    "brinstar": gradient("#0b1a12", "#030906"),
    "norfair": gradient("#1a0c09", "#4a1a0c"),
    "maridia": gradient("#06191c", "#0c3a3f"),
    "tourian": gradient("#111214", "#06070a"),
}

METROID = Scene(
    name="metroid", colors=COLORS, ground=ROCK, hero=HERO, ascii=ASCII, hero_x=16,
    layers=LAYERS, mover=ALIEN, movers=(CRAWLER,), cues=CUES, cue_rise=CUE_RISE,
    scroll_phases=frozenset({"writing"}), variants=VARIANTS, sky=SKIES["crateria"], skies=SKIES,
    hero_shot=BEAM, grounds={"norfair": LAVA, "maridia": WATER, "brinstar": GROWTH, "tourian": METAL},
    particles=PARTICLES, hero_light=("#5de06a", 3), hero_light_phases=frozenset({"needs_you"}),
)
register_scene(METROID)
