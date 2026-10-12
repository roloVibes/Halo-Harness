"""halo_harness.tui.scene_metroid -- the Metroid theme's level (Halo 3.0.2.0,
second generation): a deep cavern that darkens toward the floor. Far wall
silhouettes creep by, stalactites hang from the top, spores glow and fade,
rock pillars and a blue hatch pass at ground speed. The hunter in a power
suit runs a four-frame stride and fires charge-beam bolts that light the
rock as they fly while the model writes; a floating alien drifts in on a
sine, pulsing, while the model thinks, and latches onto the helmet on an
error; the helmet beacon blinks when it needs you. An energy tank when a
sub-agent finishes, a missile pickup when a job completes. The area sets
the floor and the sky: rock in Crateria, growth in Brinstar, lava in
Norfair (animated), water in Maridia, machine floor in Tourian. Original
art, nothing copied from any game. See tui/scene.py.
"""

from __future__ import annotations

from halo_harness.tui.scene import Layer, Mover, Scene, Shot, register_scene
from halo_harness.tui.scene_fx import gradient

COLORS = {
    "O": "#f28a1e", "V": "#5de06a", "A": "#9aa3b0", "E": "#ffb020", "G": "#7df27d", "R": "#e33b3b",
    "F": "#f4f6ff", "K": "#2d2a3e", "M": "#4a4660", "B": "#3a7bd5", "T": "#4fd1c5", "P": "#171329",
    "Z": "#9ff3ff", "g": "#4a4660", "k": "#302c40", "L": "#ff6a1a", "l": "#ffc020",
}

# The hunter, 8 x 9: round helmet with a green visor, broad shoulders, the
# arm cannon to the right, boots.
_TOP = ("..OOOO..", ".OOVVVO.", ".OOVVvO.", "..OOOO..", "OOOOOOAA", "OoOOOoAA", ".OOOOOo.")
_LEGS = ((".OO..OO.", ".oo..oo."), ("..OOOO..", "..oooo.."), (".OO..OO.", "OO....OO"), ("..OOOO..", "..oooo.."))
_STAND = _TOP + (".OO..OO.", ".oo..oo.")
HERO = {
    "idle": (_STAND,),
    "writing": tuple(_TOP + legs for legs in _LEGS),
    "thinking": (_STAND, ("..OOOO..", ".OOEEEO.", ".OOEEeO.") + _STAND[3:]),
    "error": ((".GGGGGG.", "GGRGGRGG", ".GgGGgG.", "..OOOO..", "OOOOOOAA", "OoOOOoAA", ".OOOOOo.", ".OO..OO.", ".oo..oo."),),
    "needs_you": (_STAND, ("..EEEE..", ".OOVVVO.") + _STAND[2:]),
}

# The charge beam: bolts fly right while the model writes and light the rock.
BEAM = Shot(frames=(("ZZZZ", "zZZz"), ("zZZZ", "ZZzz")), speed=4, every=8, life=28, y=3, dx=1, light=("#9ff3ff", 3))

# The alien, 9 x 7, two pulse frames; it floats and bobs.
ALIEN = Mover(frames=(("..GGGGG..", ".GGRGRGG.", "GGRGGGRGG", ".GGGGGGG.", "..gGgGg..", "..F.F.F..", "..F.F.F.."),
                      ("..ggggg..", ".GGRGRGG.", "GgRGGGRgG", ".GGGgGGG.", "..GgGgG..", "..F.F.F..", "...F.F...")),
              phases=frozenset({"thinking"}), speed=1, y=2, bob=2)

WALL = ("...PPPP.....", "..PPPPPP..PP", ".PPPPPPP.PPP", ".PPPPPPPPPPP", "PPPPPPPPPPPP", "PPPPPPPPPPPP", "PPPPPPPPPPPP", "PPPPPPPPPPPP", "PPPPPPPPPPPP")
STALACTITE = ("MMMMM", ".MMM.", ".mMm.", "..m..")
SPORE = ("T",)
PILLAR_TALL = (".KMK.", ".KMMK", "KKMMK", "KkMMK", "KkMmK", "KKMMK", "KKmmK")
BOULDER = (".MMM.", "MMmMM", "kMmmk")
HATCH = ("BBBBBB", "BbEEbB", "BbEEbB", "BbEEbB", "BbEEbB", "BbEEbB", "bbbbbb")

LAYERS = (
    Layer(sprites=(WALL,), spacing=43, speed=0.3, y=0),
    Layer(sprites=(STALACTITE,), spacing=29, speed=0.6, y=5),
    Layer(sprites=(SPORE,), spacing=23, speed=0.8, y=4, twinkle=3, light=("#4fd1c5", 2)),
    Layer(sprites=(HATCH,), spacing=113, speed=1.0, y=0),
    Layer(sprites=(PILLAR_TALL, BOULDER, PILLAR_TALL), spacing=47, speed=1.0, y=0),
)

ROCK = (("MMmMMMmM", "KkKKkKKK", "KKKKKKKK"),)
LAVA = (("LlLLLlLL", "LLLlLLLL", "llllllll"), ("LLlLLLlL", "lLLLLlLL", "llllllll"), ("LLLlLLLL", "LlLLlLLL", "llllllll"))

CUES = {
    "agent_done": ("EEEE", "EOOE", "EOOE", "EEEE"),   # an energy tank
    "job_done": (".R.", "RRR", "FFF", "F.F"),         # a missile pickup
}

ASCII = {
    "hero": (" A ", "[o]", "/|=", "|||"),
    "mover": ("(oo)", " vv "),
    "tile": (" ||", " ||", " ||", "_||"),
    "ground": ("-",),
}

VARIANTS = {
    "crateria": {},
    "brinstar": {"g": "#3f8f4f", "k": "#2a5e34", "K": "#1f3a24", "M": "#356b3d", "P": "#0f2416"},
    "norfair": {"K": "#3a1a10", "M": "#6b3220", "P": "#2a110c"},
    "maridia": {"g": "#2b6fd6", "k": "#1a4aa0", "K": "#1a2a4a", "M": "#2f4f8a", "P": "#0c2238"},
    "tourian": {"g": "#6a6f78", "k": "#4a4f57", "K": "#2a2c30", "M": "#45484f", "P": "#1a1b1e"},
}
SKIES = {
    "crateria": gradient("#0a1220", "#03050a"),
    "brinstar": gradient("#0b1a12", "#030906"),
    "norfair": gradient("#1a0c09", "#4a1a0c"),
    "maridia": gradient("#06191c", "#0c3a3f"),
    "tourian": gradient("#111214", "#06070a"),
}


METROID = Scene(
    name="metroid", colors=COLORS, ground=ROCK, hero=HERO, ascii=ASCII, hero_x=10,
    layers=LAYERS, mover=ALIEN, cues=CUES, scroll_phases=frozenset({"writing"}), variants=VARIANTS,
    sky=SKIES["crateria"], skies=SKIES, hero_shot=BEAM, grounds={"norfair": LAVA},
)
register_scene(METROID)
